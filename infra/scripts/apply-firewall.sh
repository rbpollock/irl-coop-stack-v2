#!/usr/bin/env bash
set -euo pipefail

INSTANCE="${1:-dev}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

say()  { printf '\033[1;34m== %s\033[0m\n' "$*"; }
ok()   { printf '  \033[32mOK\033[0m   %s\n' "$*"; }
warn() { printf '  \033[33mWARN\033[0m %s\n' "$*"; }

say "Firewall generation for instance: $INSTANCE"
python3 "$ROOT/infra/build/generate-firewall.py" "$INSTANCE"

RULESET="$ROOT/infra/out/$INSTANCE/firewall.nft"
[ -f "$RULESET" ] || { fail "No generated firewall at $RULESET"; exit 1; }

say "Applying firewall"

# Disable UFW — it inserts iptables rules that fight with nftables
if command -v ufw >/dev/null && ufw status 2>/dev/null | grep -q "Status: active"; then
    warn "Disabling UFW (conflicts with nftables)"
    sudo ufw disable >/dev/null 2>&1 || true
fi

sudo nft -f "$RULESET"
ok "Rules loaded"

# Persist for boot
sudo mkdir -p /etc/nftables.d
sudo cp "$RULESET" /etc/nftables.d/irl-coop.nft
sudo tee /etc/nftables.conf >/dev/null <<'EOF'
#!/usr/sbin/nft -f
include "/etc/nftables.d/irl-coop.nft"
EOF
sudo chmod +x /etc/nftables.conf
sudo systemctl enable nftables >/dev/null 2>&1 || true

ok "Firewall applied and persisted"
say "Active rules (inet filter input):"
sudo nft list chain inet filter input | grep -E "policy|backend_ports|docker0|tailnet|443|22|drop" || true
