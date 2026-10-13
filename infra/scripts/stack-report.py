#!/usr/bin/env python3
"""irl.coop stack report — declared-vs-running, stdlib only.

Mirrors apps/coop-api/src/status.ts (the web dashboard's live endpoint) but
runs standalone on the host for boot bring-up and motd.

CLASSIFICATION (revised 2026-09-13). The old model was binary — "not running =
down" — which conflated four different things and made the report useless as a
health signal: a completed migration, a failed one-shot, a real outage and a
never-run job all landed in the same bucket, and every in-development container
inflated the total. It now separates LIFECYCLE from HEALTH:

  * lifecycle = `service` (expected running) or `job` (expected to exit)
      Read from the RESOLVED compose definition (`docker compose config
      --format json`): `restart: "no"` is the declarative marker for a one-shot.
      This is authoritative — it is the same file docker itself acts on.
  * role = `core` (the stack is unhealthy if it breaks) or `support`/`dev`.
      Read from the app spec (`infra/instances/dev/apps/*.yaml`, field `role`,
      default `core`) and matched to services by name prefix. UNKNOWN IS CORE:
      anything we cannot attribute is reported, never silently ignored.
  * health = per service, not per container count:
      running + healthcheck healthy    -> healthy
      running + healthcheck unhealthy  -> degraded   (previously invisible)
      running, no healthcheck          -> running
      job, exited 0                    -> completed  (healthy, by design)
      job, exited non-zero             -> failed
      service, exited                  -> down
      service, no container            -> not-started
      job, no container                -> not-run

Headline numbers are CORE SERVICES ONLY. Jobs, not-yet-run work and stopped
support services are reported, but they no longer masquerade as outages.

Usage:
  stack-report.py            print the human report
  stack-report.py --json P   write the JSON snapshot (superset of the old
                             shape: `/api/v1/stack/status` consumers keep
                             working) to P and print nothing
"""
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "infra", "out", "dev")
APPS = os.path.join(ROOT, "infra", "instances", "dev", "apps")
# Host-process apps (no compose, no container) — declared once in the tree and
# read by BOTH this script and apps/coop-api/src/status.ts. See the "BLIND SPOT"
# note below.
HOST_APPS = os.path.join(ROOT, "infra", "instances", "dev", "host-apps.yaml")

ONESHOT_RESTART = "no"          # the declarative marker: "do not expect me running"
DEFAULT_ROLE = "core"           # unknown is core — never silently ignore a service


def sh(args, timeout=25):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None


def spec_of(path):
    """Top-level scalars plus the `sidecars:` keys from an app spec.

    Sidecar names matter for attribution: `profiles-minio-init` and
    `chat-minio-init` belong to the `minio` app, and no prefix rule can see
    that. The tree is shallow, so this needs no YAML dependency.
    """
    spec, sidecars = {}, []
    in_sidecars = False
    try:
        with open(path) as fh:
            for line in fh:
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                indent = len(line) - len(line.lstrip(" "))
                if indent == 0:
                    in_sidecars = False
                    if ":" in line:
                        k, v = line.split(":", 1)
                        k = k.strip()
                        spec[k] = v.strip().strip('"').strip("'")
                        if k == "sidecars" and not spec[k]:
                            in_sidecars = True
                elif in_sidecars and indent == 2 and ":" in line:
                    sidecars.append(line.strip().split(":", 1)[0].strip())
    except OSError:
        return {}, []
    return spec, sidecars


def app_roles():
    """[(app_name, role, {sidecar names})] from the declarative tree.
    Longest name wins so `rag` does not swallow `rag-api`."""
    out = []
    if not os.path.isdir(APPS):
        return out
    for f in sorted(os.listdir(APPS)):
        spec, sidecars = spec_of(os.path.join(APPS, f))
        if not spec.get("name") or spec.get("enabled", "true").lower() == "false":
            continue
        # `service_name` is the spec's exact compose service when it differs
        # from the app name (citus -> `postgres`); sidecars cover the rest
        # (minio -> `profiles-minio-init`, `chat-minio-init`).
        explicit = set(sidecars)
        if spec.get("service_name"):
            explicit.add(spec["service_name"])
        out.append((spec["name"], (spec.get("role") or DEFAULT_ROLE).lower(), explicit))
    return sorted(out, key=lambda kv: -len(kv[0]))


def role_for(service, roles):
    """Attribute a service to an app: explicit sidecar name first (exact), then
    the `<app>-` family by longest prefix. Unattributed stays core."""
    for name, role, sidecars in roles:
        if service in sidecars:
            return role, name
    for name, role, sidecars in roles:
        if service == name or service.startswith(name + "-"):
            return role, name
    return DEFAULT_ROLE, None


def compose_definition(base, override=None):
    """Resolved compose as JSON: {service: {restart, healthcheck}}. The resolved
    form (not the raw YAML) so profiles/anchors/env substitution are applied by
    the same code docker uses. Falls back to a name-only view if the docker
    version cannot emit JSON — never crashes a boot report."""
    files = ["-f", base] + (["-f", override] if override and os.path.isfile(override) else [])
    r = sh(["docker", "compose", *files, "config", "--format", "json"])
    if r and r.returncode == 0 and (r.stdout or "").strip().startswith("{"):
        try:
            svc = json.loads(r.stdout).get("services", {}) or {}
            return {n: {"restart": (v or {}).get("restart"), "healthcheck": bool((v or {}).get("healthcheck"))}
                    for n, v in svc.items()}, True
        except ValueError:
            pass
    r = sh(["docker", "compose", *files, "config", "--services"])
    names = [s for s in (r.stdout or "").splitlines() if s.strip()] if r and r.returncode == 0 else []
    return {n: {"restart": None, "healthcheck": False} for n in names}, False


def zk_probe():
    """P2 proving-layer status for the report's declared-vs-running view.

    zk-proving is not a compose service — it's a bootstrap whose artifact (a
    Groth16 verifier + key) plugs into the pool. Present it as a single row so a
    missing setup is a visible red flag, not a silent gap (per the flag-not-fatal
    rule). stdlib-only, no network.
    """
    spec_path = os.path.join(APPS, "zk-proving.yaml")
    if not os.path.isfile(spec_path):
        return {"declared": False, "status": "undeclared"}
    # enabled? read via the same shallow spec parse
    enabled = True
    try:
        for line in open(spec_path):
            if line.startswith("enabled:"):
                enabled = line.split(":", 1)[1].strip().lower() != "false"
    except OSError:
        enabled = True
    key_dir = os.environ.get("ZK_KEY_DIR", "/mnt/storage/zk/keys")
    name = "spend"  # single-key-per-pool decision
    vk = os.path.join(key_dir, f"{name}_vk.json")
    proving = os.path.join(key_dir, f"{name}_final.zkey")
    have = os.path.isfile(vk) and os.path.isfile(proving)
    if not enabled:
        status = "declared (not wired)"
    elif have:
        status = "setup present — verifier can be wired"
    else:
        status = "KEY MISSING — run the one-time ceremony (flag, not fatal)"
    return {
        "declared": True,
        "enabled": enabled,
        "key_dir": key_dir,
        "have_setup": have,
        "status": status,
    }


def host_app_specs():
    """The host-process fleet from `infra/instances/dev/host-apps.yaml`.

    BLIND SPOT this closes: these apps have no docker-compose, so the
    reconciler — whose view of the world is `docker ps` — could not see them at
    all. On 2026-10-03 the report read "61/61 core services healthy" while
    https://api.irl.coop had been 502 for four days (a mid-edit compile error
    killed the coop-api dev server; ts-node-dev never respawned). A health
    headline that cannot see a dead canonical API is worse than no headline.

    Shallow 2-space parse (list of `- name:` items with scalar fields), stdlib
    only, mirroring spec_of().
    """
    out, cur = [], None
    try:
        with open(HOST_APPS) as fh:
            for line in fh:
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                indent = len(line) - len(line.lstrip(" "))
                body = line.strip()
                if indent == 0:
                    cur = None                      # the `hosts:` key itself
                    continue
                if body.startswith("- "):
                    cur = {}
                    out.append(cur)
                    body = body[2:]
                if cur is None or ":" not in body:
                    continue
                k, v = body.split(":", 1)
                cur[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        return []
    specs = []
    for h in out:
        try:
            h["port"] = int(h.get("port") or 0)
        except ValueError:
            continue
        if h.get("name") and h["port"]:
            specs.append(h)
    return specs


def host_probe(port, path="/", probe="http", timeout=3):
    """Liveness of ONE host process. Returns (healthy, human detail).

    Probes 127.0.0.1:<port> — the same address the edge targets through the
    docker gateway, and the only thing that actually proves the process is
    serving (its supervisor pid can look perfectly healthy while nothing is
    bound; see the 2026-10-03 outage).
    """
    if probe == "jsonrpc":
        payload = b'{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/", data=payload,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return (r.status == 200), ("answering" if r.status == 200 else f"HTTP {r.status}")
        except Exception as exc:
            return False, "not answering"
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path or '/'}", timeout=timeout) as r:
            ok = 200 <= r.status < 400
            return ok, ("answering" if ok else f"HTTP {r.status}")
    except urllib.error.HTTPError as exc:
        # A live server that answers 401/403 IS up — only a refused/timed-out
        # connection means the process is gone.
        return True, f"answering (HTTP {exc.code})"
    except Exception:
        return False, "not answering"


def declared_composes():
    """[(id, kind, pillar, base, {service: {restart, healthcheck}}, resolved)]"""
    out = []
    cdir = os.path.join(OUT, "compose")
    if os.path.isdir(cdir):
        for pillar in sorted(os.listdir(cdir)):
            base = os.path.join(cdir, pillar, "docker-compose.yml")
            if not os.path.isfile(base):
                continue
            defn, resolved = compose_definition(base, base.replace(".yml", ".override.yml"))
            if defn:
                out.append((f"tree:{pillar}", "tree", pillar, base, defn, resolved, None))
    if os.path.isdir(APPS):
        for f in sorted(os.listdir(APPS)):
            spec, _ = spec_of(os.path.join(APPS, f))
            if spec.get("type") != "source" or not spec.get("source"):
                continue
            src = spec["source"]
            if not os.path.isabs(src):
                src = os.path.join(ROOT, src)
            base = os.path.join(src, "docker-compose.yml")
            if not os.path.isfile(base):
                continue
            defn, resolved = compose_definition(base)
            if defn:
                out.append((f"source:{spec['name']}", "source", spec.get("pillar", "source"),
                            base, defn, resolved, spec["name"]))
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
            rec = {
                "name": (j.get("Names") or "").lstrip("/"),
                "image": j.get("Image") or "",
                "state": j.get("State") or "",
                "status": j.get("Status") or "",
                "exit_code": None,
                "health": None,
                "ports": j.get("Ports") or "",
                "project": labels.get("com.docker.compose.project") or "",
                "service": labels.get("com.docker.compose.service") or "",
                "configFiles": [p.strip() for p in (labels.get("com.docker.compose.project.config_files") or "").split(",") if p.strip()],
            }
            m = re.search(r"\(([a-z]+)\)", rec["status"])
            if m:
                rec["health"] = m.group(1)
            m = re.search(r"Exited \((\d+)\)", rec["status"])
            if m:
                rec["exit_code"] = int(m.group(1))
            out.append(rec)
        except (ValueError, KeyError):
            continue
    return out


def classify(container, lifecycle):
    """The per-service answer to 'how healthy is this one?'"""
    if container is None:
        return "not-run" if lifecycle == "job" else "not-started"
    state, health = container["state"], container["health"]
    if state == "running":
        if health == "unhealthy":
            return "degraded"
        if health == "healthy":
            return "healthy"
        return "running"
    if state in ("paused", "restarting", "created", "dead"):
        return "degraded" if state == "dead" else state
    if state == "exited":
        if lifecycle == "job":
            return "completed" if container["exit_code"] == 0 else "failed"
        return "down"
    return state or "unknown"


# health values that mean "this one is fine"
OK_STATES = {"healthy", "running", "completed"}
# health values that mean "a human should look"
BAD_STATES = {"degraded", "failed", "down", "not-started", "dead"}


def reconcile():
    containers = docker_containers()
    if containers is None:
        return {"error": "docker_unavailable", "pillars": [], "orphans": []}
    decls = declared_composes()
    roles = app_roles()
    matched = set()
    pillars = []
    for did, kind, pillar, base, defn, resolved, owner in decls:
        project = os.path.basename(os.path.dirname(base))
        rows = []
        for svc, meta in sorted(defn.items()):
            lifecycle = "job" if (meta.get("restart") == ONESHOT_RESTART) else "service"
            c = next((x for x in containers if x["project"] == project and x["service"] == svc), None)
            if c:
                matched.add(c["name"])
            # a `type: source` compose belongs wholly to its app — its service
            # names (`web`, `api`, `worker`, `migrator`) carry no prefix to match
            if owner:
                role = next((r for n, r, _ in roles if n == owner), DEFAULT_ROLE)
                app = owner
            else:
                role, app = role_for(svc, roles)
            health = classify(c, lifecycle)
            rows.append({
                "service": svc,
                "app": app,
                "role": role,
                "lifecycle": lifecycle,
                "health": health,
                "healthy": health in OK_STATES,
                "container": {
                    "name": c["name"], "state": c["state"], "health": c["health"],
                    "status": c["status"], "image": c["image"], "ports": c["ports"],
                    "exit_code": c["exit_code"],
                } if c else None,
            })
        problems = [r for r in rows if not r["healthy"] and r["role"] == "core"]
        pillars.append({
            "id": did, "pillar": pillar, "kind": kind, "compose": base,
            "resolved": resolved,
            "declared": len(rows),
            "services": sum(1 for r in rows if r["lifecycle"] == "service"),
            "jobs": sum(1 for r in rows if r["lifecycle"] == "job"),
            "up": sum(1 for r in rows if r["container"] and r["container"]["state"] == "running"),
            "problems": len(problems),
            "problem_services": [r["service"] for r in problems],
            "missing": [r["service"] for r in rows if not r["container"]],
            "rows": rows,
        })
    orphans = sorted(
        [{"name": c["name"], "image": c["image"], "state": c["state"], "status": c["status"],
          "project": c["project"], "compose": (c["configFiles"] or [None])[0]}
         for c in containers if c["name"] not in matched],
        key=lambda o: o["name"],
    )

    allrows = [r for p in pillars for r in p["rows"]]
    core = [r for r in allrows if r["role"] == "core"]
    core_svc = [r for r in core if r["lifecycle"] == "service"]
    jobs = [r for r in allrows if r["lifecycle"] == "job"]
    state_counts = {}
    for r in allrows:
        state_counts[r["health"]] = state_counts.get(r["health"], 0) + 1

    # Host processes: no container, so `docker ps` cannot see them. Probed on
    # their own port and surfaced in the headline (see host_app_specs()).
    host_apps = []
    for h in host_app_specs():
        healthy, detail = host_probe(h["port"], h.get("health") or "/", h.get("probe") or "http")
        host_apps.append({
            "name": h["name"],
            "port": h["port"],
            "role": (h.get("role") or DEFAULT_ROLE).lower(),
            "description": h.get("description") or "",
            "probe": h.get("probe") or "http",
            "healthy": healthy,
            "status": detail,
        })

    return {
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "stack_root": ROOT,
        "summary": {
            # --- headline: CORE SERVICES ONLY. This is the number a live claim may show.
            "core_services": len(core_svc),
            "core_healthy": sum(1 for r in core_svc if r["healthy"]),
            "core_problems": sum(1 for r in core_svc if not r["healthy"]),
            # --- everything, still reported so nothing is hidden
            "declared": len(allrows),
            "containers": len(containers),
            "up": sum(1 for r in allrows if r["container"] and r["container"]["state"] == "running"),
            "services": sum(1 for r in allrows if r["lifecycle"] == "service"),
            "jobs": len(jobs),
            "jobs_completed": sum(1 for r in jobs if r["health"] == "completed"),
            "jobs_failed": sum(1 for r in jobs if r["health"] == "failed"),
            "jobs_not_run": sum(1 for r in jobs if r["health"] == "not-run"),
            "degraded": sum(1 for r in allrows if r["health"] == "degraded"),
            "healthy": sum(1 for c in containers if c["health"] == "healthy"),
            "orphans": len(orphans),
            "by_state": state_counts,
            # --- kept for old consumers: "down" now means CORE SERVICES ACTUALLY DOWN
            "down": sum(1 for r in core_svc if not r["healthy"]),
            "not_attributed": sum(1 for r in allrows if not r["app"]),
            # --- host processes: no container, so `docker ps` never sees them.
            # Counted separately (they are not compose services) but ALWAYS
            # shown in the headline — this is the leg that was missing when
            # api.irl.coop sat 502 behind a green report for four days.
            "host_apps": len(host_apps),
            "host_healthy": sum(1 for h in host_apps if h["healthy"]),
            "core_host_apps": sum(1 for h in host_apps if h["role"] == "core"),
            "core_host_healthy": sum(1 for h in host_apps if h["role"] == "core" and h["healthy"]),
            "core_host_problems": sum(1 for h in host_apps if h["role"] == "core" and not h["healthy"]),
        },
        "roles": {name: role for name, role, _ in roles},
        "pillars": pillars,
        "host_apps": host_apps,
        "orphans": orphans,
        "zk": zk_probe(),
    }


def fmt(data):
    if "error" in data:
        return f"irl.coop stack: {data['error']}"
    s = data["summary"]
    parts = []
    if s["core_problems"]:
        parts.append(f"\033[31m✗ {s['core_problems']} of {s['core_services']} core services need attention\033[0m")
    else:
        parts.append(f"\033[32m✓ {s['core_healthy']}/{s['core_services']} core services healthy\033[0m")
    # Host processes get their own bucket in the headline: they have no
    # container, so a dead one (api.irl.coop, 2026-09-29 → 10-03) used to leave
    # the line above reading all-green.
    if s.get("core_host_apps"):
        if s.get("core_host_problems"):
            parts.append(f"\033[31m✗ {s['core_host_problems']} of {s['core_host_apps']} host app(s) DOWN\033[0m")
        else:
            parts.append(f"\033[32m✓ {s['core_host_healthy']}/{s['core_host_apps']} host apps healthy\033[0m")
    lines = [f"irl.coop stack — {' · '.join(parts)}"]
    bits = []
    if s["jobs"]:
        bits.append(f"{s['jobs_completed']}/{s['jobs']} one-shot jobs completed"
                    + (f", \033[31m{s['jobs_failed']} failed\033[0m" if s["jobs_failed"] else ""))
    if s["degraded"]:
        bits.append(f"\033[33m{s['degraded']} degraded\033[0m")
    if s["jobs_not_run"]:
        bits.append(f"{s['jobs_not_run']} job(s) not run")
    bits.append(f"{s['orphans']} undeclared container(s)")
    lines.append("  " + " · ".join(bits))
    zk = data.get("zk")
    if zk and zk.get("declared"):
        _mark = "\033[33mFLAG\033[0m" if not zk.get("have_setup") and zk.get("enabled") else (
            "\033[2m—\033[0m" if not zk.get("enabled") else "\033[32mOK\033[0m")
        lines.append(f"  {_mark} zk-proving  [{zk['status']}]")
    if s.get("host_apps"):
        bad = [h for h in data["host_apps"] if not h["healthy"]]
        dev = sum(1 for h in data["host_apps"] if h["role"] != "core")
        mark = "\033[32mOK\033[0m" if not bad else f"\033[31m{len(bad)} ISSUE(S)\033[0m"
        lines.append(f"  {mark} {'host apps':<18} {s['core_host_healthy']}/{s['core_host_apps']} core"
                     + (f", {dev} dev" if dev else "")
                     + "  (no container — probed on its port)")
        for h in data["host_apps"]:
            if h["healthy"]:
                continue
            colour = "\033[31m" if h["role"] == "core" else "\033[33m"
            lines.append(f"        {colour}✗ {h['name']} (:{h['port']})\033[0m [{h['status']}]")
    for p in data["pillars"]:
        mark = "\033[32mOK\033[0m" if p["problems"] == 0 else f"\033[31m{p['problems']} ISSUE(S)\033[0m"
        label = p["pillar"] if p["kind"] == "tree" else f"{p['id'].split(':', 1)[1]} (source)"
        lines.append(f"  {mark} {label:<18} {p['services']} service(s), {p['jobs']} job(s)")
        for r in p["rows"]:
            if r["healthy"]:
                continue
            st = r["container"]["status"] if r["container"] else "no container"
            colour = "\033[31m" if r["role"] == "core" and r["lifecycle"] == "service" else "\033[33m"
            lines.append(f"        {colour}✗ {r['service']}\033[0m [{r['health']}, {r['lifecycle']}"
                         f"{', ' + r['role'] if r['role'] != 'core' else ''}] ({st})")
    if data["summary"].get("not_attributed"):
        lines.append(f"  \033[33m{s['not_attributed']} service(s) not attributed to an app spec "
                     f"— treated as core\033[0m")
    if data["orphans"]:
        lines.append("  \033[33mundeclared (dev spikes / old runs, informational):\033[0m")
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
