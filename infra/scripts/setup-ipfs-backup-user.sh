#!/usr/bin/env bash
# Set up the off-host backup account on the IPFS box (137.184.24.48).
#
# Why a script: the box-side setup is a sequence of small, order-sensitive steps
# (key placement, ownership, permissions, password lockout), and doing it by hand
# once leaves no record of how it was configured. This is the runbook.
#
# Design constraints it encodes:
#   - the backup account needs NO sudo and never touches the IPFS repo directory —
#     it talks to the local kubo API over 127.0.0.1:5001, which any local user can reach;
#   - the key is source-restricted (from=) so a copy of it is useless off this host;
#   - sshd hardening is NOT applied here (a mistake locks you out) — it is printed.
#
# Run as root ON THE IPFS BOX:   bash setup-ipfs-backup-user.sh
# Idempotent: safe to re-run.
set -euo pipefail

USERNAME="${USERNAME:-irlbackup}"
HOME_DIR="/home/$USERNAME"
BACKUP_DIR="$HOME_DIR/restic"

PUBKEY='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILrrYt5BOWp32qxaWvFxMR4Ga9HvSivXtGqgIxHnBMaF irl.coop stack backup -> ipfs.nftbookbazaar.com'
FROM_RESTRICT='from="64.135.141.73,192.168.18.20,100.122.136.95"'

[ "$(id -u)" = 0 ] || { echo "run as root" >&2; exit 1; }

echo "=== 1. the account ==="
if id "$USERNAME" >/dev/null 2>&1; then
  echo "  $USERNAME exists (leaving it alone)"
else
  useradd -m -s /bin/bash "$USERNAME"
  echo "  created $USERNAME"
fi
usermod --lock "$USERNAME" >/dev/null 2>&1 && echo "  password locked (key-only account)"

echo "=== 2. the key (source-restricted) ==="
install -d -m 700 -o "$USERNAME" -g "$USERNAME" "$HOME_DIR/.ssh"
printf '%s %s\n' "$FROM_RESTRICT" "$PUBKEY" > "$HOME_DIR/.ssh/authorized_keys"
chown "$USERNAME:$USERNAME" "$HOME_DIR/.ssh/authorized_keys"
chmod 600 "$HOME_DIR/.ssh/authorized_keys"
echo "  installed for $USERNAME, restricted to 64.135.141.73 / LAN / tailnet"

echo "=== 3. take our key OFF root (it has no business there) ==="
if [ -f /root/.ssh/authorized_keys ] && grep -qF "$PUBKEY" /root/.ssh/authorized_keys; then
  cp /root/.ssh/authorized_keys "/root/.ssh/authorized_keys.bak.$(date +%s)"
  grep -vF "$PUBKEY" /root/.ssh/authorized_keys > /tmp/_ak && cat /tmp/_ak > /root/.ssh/authorized_keys
  rm -f /tmp/_ak
  echo "  removed from /root/.ssh/authorized_keys (backup kept alongside)"
else
  echo "  not present on root — nothing to remove"
fi

echo "=== 4. landing directory for the repository ==="
install -d -m 750 -o "$USERNAME" -g "$USERNAME" "$BACKUP_DIR"
echo "  $BACKUP_DIR"

echo "=== 5. rsync (the backup transfers with it) ==="
if command -v rsync >/dev/null 2>&1; then
  echo "  present"
elif command -v apt-get >/dev/null 2>&1; then
  apt-get update -qq && apt-get install -y -qq rsync && echo "  installed"
elif command -v dnf >/dev/null 2>&1; then
  dnf install -y -q rsync && echo "  installed"
else
  echo "  MISSING and no known package manager — install rsync manually"
fi

echo
echo "=== report ==="
echo "--- can $USERNAME reach the kubo API? (this decides the design) ---"
su - "$USERNAME" -c 'curl -s --max-time 10 -X POST http://127.0.0.1:5001/api/v0/version || echo "(no response)"'
echo
echo "--- ipfs CLI on $USERNAME's PATH? ---"
su - "$USERNAME" -c 'command -v ipfs || echo "not on PATH (fine — curl to the API is enough)"'
echo
echo "--- ipfs repo size / disk ---"
su - "$USERNAME" -c 'curl -s --max-time 10 -X POST "http://127.0.0.1:5001/api/v0/repo/stat?size-only=false" 2>/dev/null | head -c 400; echo'
df -h "$BACKUP_DIR" | tail -1
echo
echo "--- sshd restrictions that could affect $USERNAME ---"
grep -hiE '^\s*(AllowUsers|DenyUsers|AllowGroups|DenyGroups|PasswordAuthentication|PermitRootLogin)' \
  /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf 2>/dev/null | sed 's/^/  /' || echo "  (none found)"
echo
echo "=== done. Do NOT change sshd yet — verify key login from the stack host first. ==="
echo "=== then, and only then, on this box: ==="
echo '    printf "%s\n" "PasswordAuthentication no" "PermitRootLogin prohibit-password" > /etc/ssh/sshd_config.d/99-irl-coop-hardening.conf'
echo "    sshd -t && systemctl reload sshd"