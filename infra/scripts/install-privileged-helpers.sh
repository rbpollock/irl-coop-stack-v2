#!/usr/bin/env bash
# Install the root-run maintenance helpers and grant `service` NOPASSWD for RUNNING them.
#
# ── THE SECURITY PROPERTY, which is the entire point ────────────────────────────────────────
#
# A sudoers rule is only as narrow as the thing it grants. `NOPASSWD: /home/service/.../*.sh`
# would be UNCONDITIONAL ROOT, because that directory belongs to the account being granted:
# replace a script, run it as root, done. So this installer does not do that.
#
# What it does instead:
#   - copies the granted scripts into /usr/local/sbin/irl-coop, owned root:root, mode 0755
#   - that DIRECTORY is root-owned and not writable by the granted user
#   - the sudoers rules name explicit file paths, with no wildcards
#
# Net effect: the account may RUN these exact programs as root, and cannot change what they
# do without the owner's password. That is the difference between a convenience and a
# backdoor, and it is the reason updating a granted script still requires sudo.
#
# Consequence to accept knowingly: a script in this set can do anything root can. Keep the
# list SHORT, keep the scripts argument-free or hardcoded, and add one only when it must.
# Anything that does not genuinely need root belongs in the repo and runs as the user
# (rebalance-to-secondary.sh, backup.sh, backup-ipfs.sh, golden-images.sh all do).
#
# Run as root, once (or again to update — which needs your password):
#     sudo bash infra/scripts/install-privileged-helpers.sh
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST_DIR="/usr/local/sbin/irl-coop"
SUDOERS="/etc/sudoers.d/irl-coop"
RUNAS_USER="${RUNAS_USER:-service}"

# Keep this list short and explicit. Each entry is root-equivalent for this user.
SCRIPTS=(
  move-docker-dataroot.sh      # moves /var/lib/docker to the secondary disk
)

[ "$(id -u)" = 0 ] || { echo "run as root" >&2; exit 1; }

# ── is /etc/sudoers.d actually included? ────────────────────────────────────────────────────
if grep -qsE '^[[:space:]]*(@|#)includedir[[:space:]]+/etc/sudoers\.d' /etc/sudoers; then
  echo "ok: /etc/sudoers includes /etc/sudoers.d"
else
  echo "WARNING: /etc/sudoers does not appear to include /etc/sudoers.d — the rule would be"
  echo "         inert. Check /etc/sudoers before continuing." >&2
fi

# ── install the programs, root-owned, into a root-owned directory ───────────────────────────
install -d -o root -g root -m 0755 "$DEST_DIR"
for s in "${SCRIPTS[@]}"; do
  [ -f "$SRC_DIR/$s" ] || { echo "missing source script: $SRC_DIR/$s" >&2; exit 1; }
  install -o root -g root -m 0755 "$SRC_DIR/$s" "$DEST_DIR/$s"
  echo "installed  $DEST_DIR/$s"
done
# the source repo copies stay user-owned and user-editable; only these installed copies are
# granted, and they are not writable by the user
chown -R root:root "$DEST_DIR"
chmod 0755 "$DEST_DIR"

# ── the rule, validated before it is installed ──────────────────────────────────────────────
# A broken file in /etc/sudoers.d can lock sudo out entirely, so it is written to a temp file,
# checked with `visudo -cf`, and only then put in place with the correct mode (0440).
tmp="$(mktemp)"
{
  echo "# irl.coop — NOPASSWD for RUNNING the root maintenance helpers in $DEST_DIR."
  echo "# Those files and their directory are root-owned, so this grants execution, NOT the"
  echo "# ability to change what executes. Update them with the owner's password."
  echo "#"
  echo "# !requiretty is included because the agent runs non-interactively (no TTY); without it"
  echo "# a non-interactive sudo would be refused even with NOPASSWD."
  echo "Defaults:$RUNAS_USER !requiretty"
  for s in "${SCRIPTS[@]}"; do
    echo "$RUNAS_USER ALL=(root) NOPASSWD: $DEST_DIR/$s"
  done
} > "$tmp"

if ! visudo -cf "$tmp"; then
  echo "sudoers validation FAILED — nothing was installed" >&2
  rm -f "$tmp"
  exit 1
fi
install -o root -g root -m 0440 "$tmp" "$SUDOERS"
rm -f "$tmp"
echo "installed  $SUDOERS"

echo
echo "── verify ────────────────────────────────────────────────────────────────────────────────"
visudo -c
echo
echo "Granted to $RUNAS_USER:"
for s in "${SCRIPTS[@]}"; do echo "  $DEST_DIR/$s"; done
echo
echo "Revoke everything:  rm $SUDOERS   (and the programs stop being root-runnable immediately)"
echo "Update a script:    edit the repo copy, then re-run this installer with your password"
echo "                    — which is exactly the property that makes the grant safe."