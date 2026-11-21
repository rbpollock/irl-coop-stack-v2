
# Secure remote desktop locked to tailnet

**Status: operational guide · 2026-11-20.**

Your Windows desktop at `desktop-3ak104a.tail50e51f.ts.net` (100.66.59.61) can
connect to this Linux server over RDP. We lock it to the tailnet — no exposure
to LAN or WAN.

## Current state

- xrdp is installed but stopped
- xrdp.ini binds to `*:3389` (all interfaces) — insecure
- nftables ruleset is currently **empty** (host is unprotected)
- Tailscale interface: `tailscale0` at `100.123.127.108`
- Your Windows client: `desktop-3ak104a` at `100.66.59.61`

## Option A: SSH tunnel (safest — no open port)

Bind xrdp to localhost only. Access it through an SSH tunnel over tailnet.

### Server-side (one-time setup)

```bash
sudo tee /etc/xrdp/xrdp.ini.d/tailnet.conf << 'EOF'
[globals]
port=tcp://127.0.0.1:3389
EOF

sudo systemctl restart xrdp
sudo systemctl enable xrdp
```

### Client-side (each session)

On your Windows 11 PC, in PowerShell or WSL:

```powershell
ssh -L 13389:localhost:3389 irl-server-01.tail50e51f.ts.net
```

Then connect Windows Remote Desktop to `localhost:13389`.

**Pros:** No firewall hole at all. Encrypted end-to-end by SSH. Even if xrdp
has a vulnerability, it is unreachable except via the tunnel.

**Cons:** Extra step to open the tunnel first.

---

## Option B: tailscale0-bound + source IP lock (convenient native RDP)

Bind xrdp to the tailscale IP and restrict nftables to your Windows client only.

### Step 1: harden xrdp

```bash
# Backup original
sudo cp /etc/xrdp/xrdp.ini /etc/xrdp/xrdp.ini.bak.$(date +%s)

# Replace the port line to bind to tailscale IP only
sudo sed -i 's/^port=3389$/port=tcp:\/\/100.123.127.108:3389/' /etc/xrdp/xrdp.ini

# Verify
grep "^port=" /etc/xrdp/xrdp.ini
```

### Step 2: add nftables rule for RDP (tailnet client only)

Add this to your repo firewall before the final drop:

```nft
# RDP — tailnet client desktop-3ak104a only
ip saddr 100.66.59.61 iifname "tailscale0" tcp dport 3389 accept
```

Exact placement in `infra/instances/dev/firewall.nft`:
```
          # Docker bridges → host backends
          ip saddr 172.16.0.0/12 tcp dport $backend_ports accept

          # RDP — tailnet-only, single client
          ip saddr 100.66.59.61 iifname "tailscale0" tcp dport 3389 accept

          log prefix "nft-input-drop: " flags all counter drop
```

### Step 3: apply firewall

```bash
cd ~/development/irl-coop-stack-v2
sudo bash infra/scripts/apply-firewall.sh dev
```

### Step 4: start xrdp

```bash
sudo systemctl enable xrdp
sudo systemctl start xrdp
sudo systemctl status xrdp --no-pager
```

### Step 5: connect from Windows

Open Windows Remote Desktop, enter:

```
100.123.127.108
```

Login with your Linux username and password.

**Pros:** Native RDP client, no tunnel step.

**Cons:** Port 3389 is open on tailscale0 (though filtered to one IP). If your
Windows machine is compromised, the attacker has a path to xrdp.

---

## Critical: change the system password first

xrdp authenticates via PAM (standard Linux password). After the 2026-11-08
incident, if the `service` account password has not been changed:

```bash
sudo passwd service
```

Choose a strong passphrase. This is the only thing standing between an attacker
and your desktop session if they reach port 3389.

---

## Verification checklist

| Check | Command |
|---|---|
| xrdp listening on correct address | `sudo ss -tlnp \| grep 3389` |
| Firewall loaded | `sudo nft list ruleset \| grep 3389` |
| Firewall blocks non-tailnet | From LAN: `nc -zv <lan-ip> 3389` should fail |
| Firewall allows tailnet client | From Windows: RDP connects |
| Service is auto-start | `systemctl is-enabled xrdp` |

---

## Rollback

```bash
sudo systemctl stop xrdp
sudo systemctl disable xrdp
sudo cp /etc/xrdp/xrdp.ini.bak.* /etc/xrdp/xrdp.ini  # pick the latest backup
# Remove the RDP line from firewall.nft and re-apply
```

---

## Recommendation

Use **Option A (SSH tunnel)** for day-to-day use. It is strictly safer and the
tunnel overhead is negligible on a tailnet. Use Option B only when you need
someone else to connect without teaching them SSH tunneling.
