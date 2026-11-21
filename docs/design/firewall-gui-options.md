
# GUI Firewall Management Options

**System:** Debian 12+ with nftables, LightDM/XFCE, custom generated ruleset  
**Date:** 2026-11-20  

---

## The honest answer first

Your firewall is a **generated artifact** from app specs (`apps/*.yaml`) via
`generate-firewall.py`. It uses nftables variables (`$backend_ports`), custom
chains, Docker bridge rules, and includes. No GUI firewall tool understands
this structure. Any GUI you install will either:

1. **Flush your rules and replace them** (firewalld)
2. **Show an empty or confusing view** (gufw, Cockpit without firewalld)
3. **Break the generator workflow** (you edit in GUI, generator overwrites on next run)

The best "GUI" for your setup is the **YAML editor + generator script** — it is
declarative, version-controlled, and reproducible.

That said, here are the available options:

---

## Option 1: firewalld + firewall-config (GTK GUI)

**What it is:** The standard Linux firewall GUI (Red Hat/Fedora/Debian).
Zones-based. GTK application.

**Install:**
```bash
sudo apt install firewalld firewall-config
```

**What it looks like:**
- Left panel: Zones (public, trusted, internal, docker, etc.)
- Right panel: Services, ports, sources, interfaces per zone
- Visual indicators for active/inactive rules

**The conflict:**
```
When firewalld starts:
  1. Loads its own nftables backend rules from /etc/firewalld/
  2. FLUSHES all existing nftables rules (including yours)
  3. Your /etc/nftables.conf is ignored
  4. apply-firewall.sh becomes non-functional
```

**Can they coexist?** No. firewalld owns the nftables ruleset. You would need to:
- Stop and disable nftables.service
- Migrate all rules into firewalld zones
- Rewrite apply-firewall.sh to output firewalld XML configs instead of .nft

**Verdict:** Capable GUI, but requires abandoning your current declarative
nftables setup. High migration cost.

---

## Option 2: gufw (Uncomplicated Firewall GUI)

**What it is:** Simple GTK wrapper around ufw. Designed for desktop users.

**Install:**
```bash
sudo apt install gufw
```

**What it looks like:**
- Simple on/off toggle
- Rules list: Allow/Deny, In/Out, App/Port
- Predefined app profiles (SSH, HTTP, etc.)

**The conflict:**
- ufw is already installed on your system
- apply-firewall.sh explicitly **disables ufw** because ufw inserts iptables
  rules that fight with nftables
- Modern ufw uses `iptables-nft` as its backend, which interfaces with
  nftables but creates shadow rule sets
- guff cannot represent your `$backend_ports` variable or Docker bridge rules

**Verdict:** Too simple for a server. Will break Docker networking.

---

## Option 3: Cockpit (Web-based server manager)

**What it is:** Red Hat's web console for Linux servers. Runs on port 9090.
Firewall page included.

**Install:**
```bash
sudo apt install cockpit cockpit-networkmanager
# Access: https://irl-server-01.tail50e51f.ts.net:9090
```

**What it looks like:**
- Web UI in browser
- Networking page shows interfaces, firewall zones (via firewalld)
- Can add/remove services and ports visually
- Also handles storage, services, logs, terminal

**The catch:**
- Cockpit's firewall page **requires firewalld**
- On a raw nftables system, the firewall card shows: "No firewall daemon is running"
- You would need to install firewald AND migrate to it (same problem as Option 1)

**However:** Cockpit itself is useful for other server management (logs, services,
storage, terminal in browser). The firewall page just won't work with raw nftables.

**Verdict:** Good general server tool, but firewall page needs firewalld migration.

---

## Option 4: Keep CLI, add a dashboard view

**What it is:** Instead of a firewall GUI, add a read-only dashboard page to
your irl-dashboard that shows the current nftables state.

**Implementation:**
```typescript
// apps/web/irl-dashboard/src/app/(dashboard-layout)/firewall/page.tsx
// Runs: sudo nft list ruleset
// Parses output into a pretty table
// Shows: active rules, drop counters, recent drops
```

**Pros:**
- Read-only: cannot break rules accidentally
- Shows YOUR custom rules (Docker bridges, backend_ports, tailnet rules)
- No extra packages to install
- Accessible from anywhere via the web dashboard
- Can show audit trail: last applied, who applied, from which git commit

**Cons:**
- Read-only (edits still require editing YAML + running generator)
- Needs sudo access for the dashboard backend

**Verdict:** Best fit for your architecture. Keeps the generator workflow intact.

---

## Comparative Summary

| Tool | Type | Understands nftables? | Works with generator? | Risk |
|---|---|---|---|---|
| firewall-config | GTK GUI | Yes (but takes over) | **No** | Flushes your rules |
| gufw | GTK GUI | No (uses iptables-nft) | **No** | Breaks Docker |
| Cockpit | Web UI | Only via firewalld | **No** (without migration) | Needs firewalld |
| Custom dashboard | Web UI | Yes (read-only) | **Yes** | None (read-only) |
| CLI + YAML | Terminal | Yes (native) | **Yes** | User error |

---

## Recommendation

**Primary:** Keep the CLI/YAML generator workflow. It is the most reliable for
a server with Docker and custom rules.

**Secondary:** If you want visual confirmation, install Cockpit for general
server management (logs, services, storage). Do NOT expect its firewall page
to work unless you migrate to firewalld.

**Tertiary:** Consider adding a read-only firewall status page to the
irl-dashboard. It shows the live ruleset parsed from `nft list ruleset` in a
human-readable table. No risk of accidental breakage.

---

## If you still want a GUI

Install firewalld and migrate everything:

```bash
# 1. Install
sudo apt install firewalld firewall-config

# 2. Stop nftables
sudo systemctl stop nftables
sudo systemctl disable nftables

# 3. Define zones in firewalld
sudo firewall-cmd --permanent --new-zone=irl-co-op
sudo firewall-cmd --permanent --zone=irl-co-op --add-source=100.64.0.0/10
sudo firewall-cmd --permanent --zone=irl-co-op --add-port=3001/tcp
sudo firewall-cmd --permanent --zone=irl-co-op --add-port=3010/tcp
sudo firewall-cmd --permanent --zone=irl-co-op --add-port=8787/tcp

# 4. Add public services
sudo firewall-cmd --permanent --zone=public --add-service=http
sudo firewall-cmd --permanent --zone=public --add-service=https

# 5. Reload
sudo firewall-cmd --reload

# 6. Launch GUI
firewall-config
```

**Warning:** This replaces `/etc/nftables.d/irl-coop.nft` with firewalld's
internal rules. `apply-firewall.sh` will no longer work. You would need to
rewrite the generator to output `firewall-cmd` commands instead of .nft files.

This is a significant architectural change. Only do it if you are willing to
abandon the declarative nftables workflow.
