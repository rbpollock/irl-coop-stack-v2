#!/bin/bash
set -euo pipefail

echo "=== Docker Network Diagnostic ==="

# 1. Check current NAT rules
echo ""
echo "--- iptables NAT POSTROUTING ---"
sudo iptables -t nat -L POSTROUTING -n -v 2>/dev/null | head -20 || echo "(no iptables output)"

echo ""
echo "--- nftables masquerade rules ---"
sudo nft list ruleset 2>/dev/null | grep -i masq || echo "(no masquerade rules in nftables)"

# 2. Check sysctls
echo ""
echo "--- IP forwarding ---"
sysctl net.ipv4.ip_forward 2>/dev/null || echo "(cannot read sysctl)"

# 3. Find what interface has the default route
echo ""
echo "--- Host routing ---"
ip route show | grep default || echo "(no default route?)"
WAN_IF=$(ip route show | awk '/^default/ {print $5; exit}')
echo "WAN interface: ${WAN_IF:-unknown}"

# 4. Check Docker networks used by keycloak
echo ""
echo "--- Keycloak container networks ---"
sudo docker inspect authentication-keycloak-1 --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}: {{.IPAddress}} gw={{.Gateway}}{{printf "\n"}}{{end}}'

# 5. Check if containers can reach internet via DNS (using java since keycloak has it)
echo ""
echo "--- Testing DNS from Keycloak container ---"
sudo docker exec authentication-keycloak-1 java -cp /opt/keycloak/lib/lib/main/org.keycloak.keycloak-server-spi-private-25.0.0.jar -c 'System.out.println("java present")' 2>/dev/null || true

# Better: use a temp busybox container on same network to test
echo ""
echo "--- Testing internet from docker bridge ---"
sudo docker run --rm --network container:authentication-keycloak-1 busybox:1.36 sh -c 'wget -qO- --timeout=5 https://oauth2.googleapis.com 2>&1 | head -1' || echo "(failed - likely no internet from container)"

echo ""
echo "=== Applying fixes ==="

# Fix 1: Ensure IP forwarding is enabled
if [ "$(cat /proc/sys/net/ipv4/ip_forward 2>/dev/null || echo 0)" != "1" ]; then
    echo "Enabling IPv4 forwarding..."
    sudo sysctl -w net.ipv4.ip_forward=1
    echo "net.ipv4.ip_forward=1" | sudo tee /etc/sysctl.d/99-docker-forward.conf >/dev/null
fi

# Fix 2: Ensure Docker's iptables rules are present
# Check if Docker's MASQUERADE rule exists for default bridge
if ! sudo iptables -t nat -C POSTROUTING -s 172.17.0.0/16 ! -o docker0 -j MASQUERADE 2>/dev/null; then
    echo "Adding Docker MASQUERADE for 172.17.0.0/16..."
    sudo iptables -t nat -A POSTROUTING -s 172.17.0.0/16 ! -o docker0 -j MASQUERADE
fi

# Add MASQUERADE for any docker-compose bridge networks (172.18.x, 172.20.x, etc.)
for net in $(sudo docker network ls --format '{{.Name}}' | grep -v -E '^none$|^host$'); do
    subnet=$(sudo docker network inspect "$net" --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}' 2>/dev/null || true)
    if [ -n "$subnet" ] && [ "$subnet" != "<no value>" ]; then
        iface=$(sudo docker network inspect "$net" --format '{{if .Options}}{{.Options.com.docker.network.bridge.name}}{{end}}' 2>/dev/null || true)
        iface=${iface:-br-$(sudo docker network inspect "$net" --format '{{.Id}}' | cut -c1-12)}
        if ! sudo iptables -t nat -C POSTROUTING -s "$subnet" ! -o "$iface" -j MASQUERADE 2>/dev/null; then
            echo "Adding MASQUERADE for $net ($subnet via $iface)..."
            sudo iptables -t nat -A POSTROUTING -s "$subnet" ! -o "$iface" -j MASQUERADE || true
        else
            echo "$net: MASQUERADE already present"
        fi
    fi
done

# Fix 3: Ensure nftables forward chain allows docker → WAN
# Check if there is a catch-all for established/related outbound, or specific docker bridge forwarding
if sudo nft list ruleset 2>/dev/null | grep -q "table inet filter"; then
    echo ""
    echo "nftables inet filter active — checking forward chain..."
    # The existing rules likely have 'iifname "br-*" accept' which should be enough,
    # but we need to ensure outbound from docker to WAN is not dropped.
    if ! sudo nft list chain inet filter forward 2>/dev/null | grep -q "ct state established,related accept"; then
        echo "Adding established/related accept to forward chain..."
        sudo nft add rule inet filter forward ct state established,related accept || true
    fi
    # Also ensure Docker bridge forwarding to WAN is accepted
    WAN_IF=$(ip route show | awk '/^default/ {print $5; exit}')
    if [ -n "$WAN_IF" ]; then
        # Check if there's a rule for oifname WAN IF
        if ! sudo nft list chain inet filter forward 2>/dev/null | grep -q "oifname \"$WAN_IF\""; then
            echo "Adding forward accept for docker bridges -> $WAN_IF..."
            sudo nft add rule inet filter forward iifname "br-*" oifname "$WAN_IF" accept || true
            sudo nft add rule inet filter forward iifname "docker0" oifname "$WAN_IF" accept || true
        fi
    fi
fi

echo ""
echo "=== Verification ==="
# Test from a temp container
sudo docker run --rm --network container:authentication-keycloak-1 busybox:1.36 sh -c 'wget -qO- --timeout=10 https://oauth2.googleapis.com 2>&1 | head -1' && echo "SUCCESS: container can reach Google OAuth" || echo "STILL BROKEN: check output above"
