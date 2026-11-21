
# RDP Security Assessment — Network Security Engineer Viewpoint

**Host:** irl-server-01 (100.123.127.108)  
**Client:** desktop-3ak104a (100.66.59.61, Windows 11)  
**Assessed:** 2026-11-20  
**Assessor:** Hermes (network security analysis)  

---

## 1. Threat Model

### What this host protects
- Production Keycloak realm (irl-coop) with 6 OIDC clients
- Shared Postgres with databases: irlcoop, matrix, nocodb, roundcube, stalwart, keycloak
- MinIO object storage
- Coop-api (port 3001) — group governance backend
- Tailnet mesh with 8 peers including Android devices

### Recent incident context
- 2026-11-08: attacker gained access via stolen SSH key + guest-writable Samba share
- ~3h authenticated AWS activity from this host
- Windows RDP sweep of 192.168.18.0/24 observed
- Exfil listener at 192.168.18.20:18088
- All secrets treated as compromised

### Threat actors we care about
| Actor | Capability | Motivation |
|---|---|---|
| Internet scanner | Automated exploit tools, credential stuffing | Botnet recruitment, ransomware |
| Tailnet insider | Any peer on 100.64.0.0/10 (8 devices) | Lateral movement if their device is compromised |
| LAN attacker | Physical access to 192.168.18.0/24 | Direct network access |
| Supply chain | Compromised xrdp binary or dependency | Persistent access |

### Attack surface of RDP specifically
1. **Protocol vulnerabilities** — xrdp implements RDP; historically has had buffer overflows, memory corruption (CVE-2022-23468, CVE-2024-XXX series)
2. **Credential attacks** — brute force, password spray, pass-the-hash
3. **Session hijacking** — if attacker gains local access, active RDP sessions can sometimes be hijacked
4. **Clipboard/file transfer** — RDP channels can exfil data or introduce malware
5. **Post-authentication** — once inside, the desktop session has the same privileges as the logged-in user

---

## 2. Current State Analysis

### Firewall audit
```nft
table inet filter {
    chain input {
        type filter hook input priority filter; policy drop;
        ct state established,related accept
        iif "lo" accept
        ip protocol icmp accept
        ip6 nexthdr ipv6-icmp accept
        ip saddr 192.168.18.0/24 tcp dport 22 accept
        tcp dport { 80, 443 } accept
        ip saddr 100.64.0.0/10 accept          ← TAILNET IS WIDE OPEN
        ip6 saddr fd7a:115c:a1e0::/48 accept   ← ALL IPv6 TAILNET TOO
        ip saddr 172.16.0.0/12 tcp dport { 3000, 3001, ... 9000 } accept
        log prefix "nft-input-drop: " flags all counter drop
    }
}
```

**Finding:** The tailnet rule `ip saddr 100.64.0.0/10 accept` is **too permissive**.
It allows ANY device on the tailnet to reach ANY port on this server. This includes:
- Compromised Android phones (spare-phone, roberts-s22)
- Compromised laptops (robbie-sn78s, zo-inde)
- Any future device added to the tailnet by any administrator

**Risk:** If any tailnet peer is compromised, lateral movement to this server is
unrestricted by firewall.

### xrdp configuration audit
- xrdp installed but not running
- Default config binds to `*:3389` (all interfaces)
- Session manager: `xrdp-sesman` with XFCE desktop
- Authentication: PAM via standard Linux password (`service` account)
- No TLS configured by default
- No NLA (Network Level Authentication) available in xrdp

---

## 3. Option Analysis

### Option A: SSH Local Port Forward (RECOMMENDED)

**Implementation:**
```bash
# Server: bind xrdp to localhost only
sudo sed -i 's/^port=3389$/port=tcp:\/\/127.0.0.1:3389/' /etc/xrdp/xrdp.ini
sudo systemctl enable xrdp --now

# Client: Windows PowerShell
ssh -L 13389:localhost:3389 irl-server-01.tail50e51f.ts.net
# Then RDP to localhost:13389
```

**Security analysis:**

| Control | Effectiveness |
|---|---|
| Network exposure | **Zero.** Port 3389 bound to 127.0.0.1. Not reachable from any interface. |
| Firewall requirement | None. No new INPUT rule needed. |
| Encryption | SSH provides transport encryption. RDP traffic never leaves the SSH tunnel unencrypted. |
| Authentication | Two factors: (1) SSH key to establish tunnel, (2) Linux password for xrdp session. |
| Blast radius if xrdp compromised | Attacker must first compromise SSH daemon AND know/crack the Linux password. |
| Audit trail | SSH login logged in /var/log/auth.log. RDP sesman logs separately. |

**Residual risks:**
- If attacker has stolen SSH key, they can open the tunnel. Mitigation: rotate SSH keys post-incident.
- If attacker is already on the server (local shell), they can connect to 127.0.0.1:3389. Mitigation: xrdp session is just another local session; local compromise is already game-over.
- Clipboard/file transfer through RDP remains a channel. Not a network issue.

**Operational impact:** One extra step (open SSH tunnel before RDP). Tunnel can be configured in Windows OpenSSH client config for auto-reconnect.

**Verdict:** Highest security. Marginal operational friction.

---

### Option B: Tailscale IP Bind + Source-Locked nftables

**Implementation:**
```bash
# Server: bind xrdp to tailscale IP only
sudo sed -i 's/^port=3389$/port=tcp:\/\/100.123.127.108:3389/' /etc/xrdp/xrdp.ini

# Add to firewall.nft
ip saddr 100.66.59.61 iifname "tailscale0" tcp dport 3389 accept

sudo bash infra/scripts/apply-firewall.sh dev
sudo systemctl enable xrdp --now
```

**Security analysis:**

| Control | Effectiveness |
|---|---|
| Network exposure | Limited to tailscale0 interface only. Not reachable from LAN or WAN. |
| Firewall | Source IP locked to 100.66.59.61 (desktop-3ak104a). Other tailnet peers blocked. |
| Encryption | Tailscale provides WireGuard encryption. RDP session travels encrypted. |
| Authentication | Single factor: Linux password only. No additional SSH auth layer. |
| Blast radius if xrdp compromised | Any client that can spoof or route through 100.66.59.61 could reach xrdp. |

**Residual risks:**
- **Tailscale ACL bypass:** If Tailscale ACLs are misconfigured (e.g., `*:*` default), any tailnet device can route to 100.123.127.108:3389 at the Tailscale level. The nftables rule is the only guard. If nftables is flushed or fails to load, the port is exposed.
- **Source IP spoofing within tailnet:** Difficult but theoretically possible if an attacker controls a routing node.
- **xrdp vulnerability (pre-auth):** If xrdp has a buffer overflow in the RDP handshake before authentication, this option exposes it directly to the network. Option A does not.
- **Credential brute force:** xrdp listens continuously. Automated tools could attempt password spray from the authorized source IP (if that Windows host is compromised).

**Operational impact:** Native RDP client, no tunnel step. One-time setup.

**Verdict:** Good security. Exposes xrdp daemon to network; dependent on xrdp implementation security.

---

### Option C: Tailscale SSH (Replace xrdp entirely)

**Implementation:**
```bash
# Do NOT install xrdp.
# Use Tailscale SSH + VS Code Remote / Windows Terminal SSH
# Or X11 forwarding: ssh -X irl-server-01 tailscale0 firefox
```

**Security analysis:**

| Control | Effectiveness |
|---|---|
| Network exposure | SSH on port 22, already allowed from LAN. Could restrict to tailnet. |
| Authentication | SSH key + optional Tailscale SSH key management. |
| No RDP protocol | Removes entire RDP attack surface. |
| Clipboard/file transfer | Via SSH/SFTP/SCP — controlled, not automatic. |

**Residual risks:**
- SSH is already an attack surface (patched regularly, but not zero).
- X11 forwarding has its own vulnerabilities (CVE-2023-XXXX series).

**Operational impact:** No GUI desktop. Some workflows (browser-based admin, graphical tools) become impossible or require X11 forwarding which is slow.

**Verdict:** Most secure. But may be operationally unacceptable if GUI tools are needed.

---

### Option D: xrdp with TLS + Certificate Auth (Advanced)

**Implementation:**
```bash
# Generate client certificate for desktop-3ak104a
# Configure xrdp to require TLS + client cert verification
# Add cert fingerprint check to sesman
```

**Security analysis:**
- Strong mutual authentication
- Complex to configure and maintain
- xrdp TLS support is less mature than OpenSSH's
- Certificate rotation overhead

**Verdict:** Overkill for this environment. SSH tunnel (Option A) provides equivalent security with less complexity.

---

## 4. Comparative Risk Matrix

| Risk | Option A (SSH tunnel) | Option B (Tailnet bind) | Option C (No RDP) |
|---|---|---|---|
| Pre-auth xrdp exploit | **Not exposed** | Exposed to 1 IP | No xrdp = no risk |
| Credential brute force | **SSH blocks first** | Direct to xrdp | SSH only |
| Tailnet peer compromise | **Tunnel requires SSH key** | xrdp reachable | SSH reachable |
| Firewall bypass / flush | **Port on localhost** | Port exposed on tailscale0 | SSH on 22 (LAN rule) |
| Insider threat (authorized user) | Linux password | Linux password | SSH key + Linux password |
| Operational complexity | Low | Low | Medium (no GUI) |

---

## 5. Additional Hardening (applies to all options)

### 5.1 Rotate the `service` password
```bash
sudo passwd service
```
Use a passphrase, not a password. 20+ characters, memorable.

### 5.2 Disable password authentication for SSH
Since you use SSH keys, disable password-based SSH auth:
```bash
sudo sed -i 's/^#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart sshd
```
This does not affect xrdp (PAM password is separate from SSH password auth).

### 5.3 Restrict SSH to tailnet only
```nft
# Replace the LAN-only SSH rule:
ip saddr 192.168.18.0/24 tcp dport 22 accept

# With tailnet-only SSH:
ip saddr 100.64.0.0/10 tcp dport 22 accept
```
This prevents LAN-based SSH attacks (the November incident involved LAN scanning).

### 5.4 Enable xrdp session logging
```bash
sudo sed -i 's/^LogLevel=.*/LogLevel=DEBUG/' /etc/xrdp/xrdp.ini
sudo sed -i 's/^LogLevel=.*/LogLevel=DEBUG/' /etc/xrdp/sesman.ini
```
Logs to `/var/log/xrdp.log` and `/var/log/xrdp-sesman.log`.

### 5.5 Disable unnecessary RDP channels
Edit `/etc/xrdp/sesman.ini`:
```ini
[SessionVariables]
Cliprdr=false          # Disable clipboard sharing
Drm=false              # Disable drive redirection
Rail=false             # Disable RemoteApp
```
Reduces data exfiltration paths.

### 5.6 Fail2ban for xrdp (if using Option B)
```bash
sudo apt install fail2ban
sudo tee /etc/fail2ban/jail.local << 'EOF'
[xrdp]
enabled = true
port = 3389
filter = xrdp
logpath = /var/log/xrdp-sesman.log
maxretry = 3
bantime = 3600
EOF
```
Not needed for Option A (SSH already has its own brute-force resistance).

---

## 6. Network Security Engineer Recommendation

**Primary recommendation: Option A (SSH tunnel) with the additional hardening in §5.**

Reasoning:
1. **Defense in depth:** The xrdp daemon is not reachable from any network interface. The SSH daemon is the only network-facing entry point, and it is a more battle-hardened service than xrdp.
2. **Fail-safe:** If nftables rules are accidentally flushed or the tailnet ACL is misconfigured, xrdp remains unreachable because it is bound to 127.0.0.1.
3. **Compromise recovery:** If the `service` password is weak or leaked, an attacker still cannot reach xrdp without first breaching SSH.
4. **Minimal cost:** One `ssh -L` command per session. Can be automated in Windows OpenSSH config.

**If GUI is not actually needed:** Consider Option C (Tailscale SSH only, no xrdp). Removes the entire RDP attack surface.

**Option B is acceptable** if operational friction from the tunnel is unacceptable and the additional hardening (fail2ban, TLS, channel restrictions) is implemented. But it is fundamentally less safe because xrdp is exposed to the network.

---

## 7. Implementation Commands (Option A + Hardening)

```bash
# 1. Reconfigure xrdp to localhost only
sudo cp /etc/xrdp/xrdp.ini /etc/xrdp/xrdp.ini.bak.$(date +%s)
sudo sed -i 's/^port=3389$/port=tcp:\/\/127.0.0.1:3389/' /etc/xrdp/xrdp.ini
grep "^port=" /etc/xrdp/xrdp.ini

# 2. Disable clipboard and drive redirection
sudo sed -i 's/^Cliprdr=true/Cliprdr=false/' /etc/xrdp/sesman.ini || true
sudo sed -i 's/^Drm=true/Drm=false/' /etc/xrdp/sesman.ini || true

# 3. Enable and start xrdp
sudo systemctl enable xrdp
sudo systemctl start xrdp

# 4. Rotate service password
sudo passwd service

# 5. (Optional) Restrict SSH to tailnet in firewall.nft
# Edit infra/instances/dev/firewall.nft:
#   Replace: ip saddr 192.168.18.0/24 tcp dport 22 accept
#   With:    ip saddr 100.64.0.0/10 tcp dport 22 accept
# Then: sudo bash infra/scripts/apply-firewall.sh dev

# 6. (Optional) Disable SSH password auth if using keys only
# sudo sed -i 's/^#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
# sudo systemctl restart sshd
```

**Windows client (PowerShell or OpenSSH):**
```powershell
# One-shot tunnel
ssh -L 13389:localhost:3389 irl-server-01.tail50e51f.ts.net

# Or add to $HOME\.ssh\config for persistent tunnel:
Host irl-rdp
    HostName irl-server-01.tail50e51f.ts.net
    LocalForward 13389 localhost:3389
    ServerAliveInterval 60
    ServerAliveCountMax 3
# Then: ssh irl-rdp (keeps tunnel open)
# RDP client connects to localhost:13389
```

---

## 8. Verification Checklist

| Step | Command | Expected result |
|---|---|---|
| xrdp on localhost only | `sudo ss -tlnp \| grep 3389` | `127.0.0.1:3389` only |
| No xrdp on tailscale0 | `sudo ss -tlnp \| grep 3389` | No `100.123.127.108:3389` |
| xrdp service running | `systemctl is-active xrdp` | `active` |
| Firewall unchanged | `sudo nft list ruleset \| grep 3389` | No rule for 3389 (expected) |
| SSH tunnel works | `ssh -L 13389:localhost:3389 ...` | Connects without error |
| RDP through tunnel | Windows RDP → `localhost:13389` | Desktop session opens |
| No direct RDP access | From another host: `nc -zv 100.123.127.108 3389` | Connection refused |
