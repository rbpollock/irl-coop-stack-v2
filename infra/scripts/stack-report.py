#!/usr/bin/env python3
"""irl.coop stack report — declared-vs-running, stdlib only.

Mirrors apps/coop-api/src/status.ts (the web dashboard's live endpoint) but
runs standalone on the host for boot bring-up and motd:

  * declared  = service names from every pillar compose in the generated
                tree (infra/out/dev/compose/*/) plus `type: source` apps
                (spec `source:` → their own compose), via
                `docker compose config --services`
  * running   = `docker ps -a` (compose project+service labels)
  * drift     = running containers that match no declared service (orphans)
                and declared services with no container (missing)

Usage:
  stack-report.py            print the human report
  stack-report.py --json P   write the JSON snapshot (same shape as the
                             coop-api endpoint) to P and print nothing
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "infra", "out", "dev")
APPS = os.path.join(ROOT, "infra", "instances", "dev", "apps")


def sh(args, timeout=20):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None


def declared_composes():
    """[(id, kind, pillar, compose_path, [service,...])]"""
    out = []
    if os.path.isdir(OUT):
        for pillar in sorted(os.listdir(os.path.join(OUT, "compose"))):
            base = os.path.join(OUT, "compose", pillar, "docker-compose.yml")
            if not os.path.isfile(base):
                continue
            files = ["-f", base]
            ovr = base.replace(".yml", ".override.yml")
            if os.path.isfile(ovr):
                files += ["-f", ovr]
            r = sh(["docker", "compose", *files, "config", "--services"])
            services = [s for s in (r.stdout or "").splitlines() if s.strip()] if r and r.returncode == 0 else []
            out.append((f"tree:{pillar}", "tree", pillar, base, services))
    if os.path.isdir(APPS):
        for f in sorted(os.listdir(APPS)):
            spec_path = os.path.join(APPS, f)
            spec = {}
            try:
                with open(spec_path) as fh:
                    for line in fh:
                        if ":" in line and not line.startswith(" "):
                            k, v = line.split(":", 1)
                            spec[k.strip()] = v.strip()
            except OSError:
                continue
            if spec.get("type") != "source" or not spec.get("source"):
                continue
            src = spec["source"]
            if not os.path.isabs(src):
                src = os.path.join(ROOT, src)
            base = os.path.join(src, "docker-compose.yml")
            if not os.path.isfile(base):
                continue
            r = sh(["docker", "compose", "-f", base, "config", "--services"])
            services = [s for s in (r.stdout or "").splitlines() if s.strip()] if r and r.returncode == 0 else []
            out.append((f"source:{spec['name']}", "source", spec.get("pillar", "source"), base, services))
    return out


def parse_labels(raw):
    """docker ps --format '{{json .}}' emits Labels either as a JSON object
    or as a flattened 'k=v,k=v' string (older/differing serializations),
    plus the literal '<no value>' for containers created outside compose."""
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or raw == "<no value>":
        return {}
    out = {}
    for part in raw.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k] = v
    return out


def docker_containers():
    r = sh(["docker", "ps", "-a", "--format", "{{json .}}"], timeout=30)
    if not r or r.returncode != 0:
        return None
    out = []
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            j = json.loads(line)
            labels = parse_labels(j.get("Labels"))
            out.append({
                "name": (j.get("Names") or "").lstrip("/"),
                "image": j.get("Image") or "",
                "state": j.get("State") or "",
                "status": j.get("Status") or "",
                "health": None,
                "ports": j.get("Ports") or "",
                "project": labels.get("com.docker.compose.project") or "",
                "service": labels.get("com.docker.compose.service") or "",
                "configFiles": [p.strip() for p in (labels.get("com.docker.compose.project.config_files") or "").split(",") if p.strip()],
            })
            m = __import__("re").search(r"\(([a-z]+)\)", out[-1]["status"])
            if m:
                out[-1]["health"] = m.group(1)
        except (ValueError, KeyError):
            continue
    return out


def reconcile():
    containers = docker_containers()
    if containers is None:
        return {"error": "docker_unavailable", "pillars": [], "orphans": []}
    decls = declared_composes()
    matched = set()
    pillars = []
    for did, kind, pillar, base, services in decls:
        project = os.path.basename(os.path.dirname(base))
        rows = []
        for svc in services:
            c = next((x for x in containers if x["project"] == project and x["service"] == svc), None)
            if c:
                matched.add(c["name"])
            rows.append({
                "service": svc,
                "container": {
                    "name": c["name"], "state": c["state"], "health": c["health"],
                    "status": c["status"], "image": c["image"], "ports": c["ports"],
                } if c else None,
            })
        up = sum(1 for r in rows if r["container"] and r["container"]["state"] == "running")
        missing = [r["service"] for r in rows if not r["container"]]
        pillars.append({
            "id": did, "pillar": pillar, "kind": kind, "compose": base,
            "declared": len(rows), "up": up, "down": len(rows) - up,
            "missing": missing, "services": rows,
        })
    orphans = sorted(
        [
            {"name": c["name"], "image": c["image"], "state": c["state"],
             "status": c["status"], "project": c["project"],
             "compose": (c["configFiles"] or [None])[0]}
            for c in containers if c["name"] not in matched
        ],
        key=lambda o: o["name"],
    )
    declared = sum(p["declared"] for p in pillars)
    up = sum(p["up"] for p in pillars)
    healthy = sum(1 for c in containers if c["health"] == "healthy")
    return {
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "stack_root": ROOT,
        "summary": {
            "declared": declared,
            "containers": len(containers),
            "up": up,
            "down": declared - up,
            "healthy": healthy,
            "orphans": len(orphans),
        },
        "pillars": pillars,
        "orphans": orphans,
    }


def fmt(data):
    if "error" in data:
        return f"irl.coop stack: {data['error']}"
    s = data["summary"]
    lines = [f"irl.coop stack — {s['up']}/{s['declared']} services up, {s['down']} down, "
             f"{s['healthy']} healthy, {s['orphans']} orphan(s)"]
    for p in data["pillars"]:
        mark = "\033[32mOK\033[0m" if p["down"] == 0 else "\033[31mDOWN\033[0m"
        lines.append(f"  {mark} {p['pillar']:<18} {p['up']}/{p['declared']} up")
        for r in p["services"]:
            if not r["container"] or r["container"]["state"] != "running":
                st = r["container"]["status"] if r["container"] else "missing"
                lines.append(f"        \033[31m✗ {r['service']}\033[0m ({st})")
    if data["orphans"]:
        lines.append("  \033[33mDRIFT\033[0m not declared in the tree:")
        for o in data["orphans"]:
            lines.append(f"        \033[33m{o['name']}\033[0m ({o['image']}, {o['state']})")
    return "\n".join(lines)


def main():
    args = sys.argv[1:]
    if args and args[0] == "--json":
        data = reconcile()
        with open(args[1], "w") as fh:
            json.dump(data, fh, indent=2)
        return 0 if "error" not in data else 1
    print(fmt(reconcile()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
