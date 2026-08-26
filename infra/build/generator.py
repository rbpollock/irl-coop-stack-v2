#!/usr/bin/env python3
"""irl.coop configuration-flow generator.

Reads the declarative tree (infra/instances/<name>/) and emits the deployment
artifacts into infra/out/<name>/:
  compose/<pillar>/docker-compose.yml        (+ .override.yml for dev sections)
  ansible/inventory/hosts.yml                (hosts + pillar assignment)
  keycloak/clients.yaml                      (OIDC client registry from app specs)
  plane/views/...                            (data-scoping view scripts)
  MANIFEST.md                                (what was generated from what)

Generated files are the source of truth for deployment — edit the tree, not
the artifacts. Run: uv run --with pyyaml infra/build/generator.py dev
"""
import pathlib
import sys
import shutil

import yaml

# infra/build/secrets.py — derived-key derivation (sibling). Imported via
# explicit path because its name shadows the stdlib `secrets` module.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import secrets as derived_secrets  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent

# README topology: server role -> pillars it hosts
ROLE_PILLARS = {
    "identity_data": ["proxy", "authentication", "authorization", "compliance", "finance", "storage", "cache", "communication"],
    "workflow_ops": ["proxy", "workflow", "lifecycle"],
}


def load(path):
    with open(path) as f:
        return yaml.safe_load(f)


def sanitize(name):
    # Plane silently rejects '.' and '-' in names — the provisioning engine
    # normalizes group names to alphanumeric + spaces.
    return "".join(c if c.isalnum() or c == " " else "" for c in name).strip()


def substitute(obj, domain):
    """Replace ${DOMAIN} in every string of a nested structure."""
    if isinstance(obj, str):
        return obj.replace("${DOMAIN}", domain)
    if isinstance(obj, list):
        return [substitute(i, domain) for i in obj]
    if isinstance(obj, dict):
        return {k: substitute(v, domain) for k, v in obj.items()}
    return obj


def emit_compose(apps, out_dir, inst_dir):
    """Emit a pillar compose file merging all its apps (services + sidecars)."""
    services = {}
    volumes = {}
    overrides = {}
    for app in apps:
        service_name = app.get("service_name", app["name"])
        svc = {}
        if app.get("image"):
            svc["image"] = app["image"]
        if app.get("command"):
            svc["command"] = app["command"]
        if app.get("ports"):
            svc["ports"] = app["ports"]
        if app.get("env"):
            svc["environment"] = app["env"]
        if app.get("volumes"):
            svc["volumes"] = app["volumes"]
        if app.get("depends_on"):
            svc["depends_on"] = app["depends_on"]
        if app.get("labels"):
            svc["labels"] = app["labels"]
        if app.get("healthcheck"):
            svc["healthcheck"] = app["healthcheck"]
        if app.get("extra_hosts"):
            svc["extra_hosts"] = app["extra_hosts"]
        if app.get("restart"):
            svc["restart"] = app["restart"]
        if app.get("network_mode"):
            svc["network_mode"] = app["network_mode"]
        services[service_name] = svc
        if app.get("dev"):
            overrides[service_name] = dict(app["dev"])
        for name, side in (app.get("sidecars") or {}).items():
            side = dict(side)
            if "dev" in side:
                overrides[name] = dict(side.pop("dev"))
            services[name] = side
        volumes.update(app.get("named_volumes", {}))
    compose = {"services": services}
    if volumes:
        compose["volumes"] = volumes
    with open(out_dir / "docker-compose.yml", "w") as f:
        yaml.safe_dump(compose, f, sort_keys=False, default_flow_style=False)
    # dev overrides (published ports / local paths), merged per service — the
    # main app service AND any sidecar that declares its own `dev:` block.
    # Host paths in dev.volumes are relative to the INSTANCE dir — absolutize
    # them so generated artifacts never hold volatile relative data.
    for dev in overrides.values():
        if dev.get("volumes"):
            dev["volumes"] = [
                str(inst_dir / v.split(":")[0]) + ":" + ":".join(v.split(":")[1:]) if v.startswith("./") else v
                for v in dev["volumes"]
            ]
    if overrides:
        with open(out_dir / "docker-compose.override.yml", "w") as f:
            yaml.safe_dump({"services": overrides}, f, sort_keys=False, default_flow_style=False)


def emit_inventory(instance, apps, out_dir):
    hosts = {}
    for role, host in instance["hosts"].items():
        pillars = [p for p in ROLE_PILLARS.get(role, []) if any(a["pillar"] == p for a in apps)]
        hosts[role] = {"hosts": {host: {}}, "vars": {"ansible_user": "app", "pillars": pillars}}
    inventory = {"all": {"children": hosts}}
    path = out_dir / "ansible" / "inventory"
    path.mkdir(parents=True, exist_ok=True)
    with open(path / "hosts.yml", "w") as f:
        yaml.safe_dump(inventory, f, sort_keys=False)


def emit_clients(instance, apps, out_dir):
    clients = {}
    for app in apps:
        oidc = app.get("oidc")
        if not oidc:
            continue
        redirects = []
        if app.get("web") and oidc.get("redirect"):
            redirects.append(f"{app['web']}{oidc['redirect']}")
        elif oidc.get("redirects"):
            redirects = oidc["redirects"]
        clients[oidc["client_id"]] = {
            "app": app["name"],
            "redirect_uris": redirects,
            "public": oidc.get("public", False),
        }
    path = out_dir / "keycloak"
    path.mkdir(parents=True, exist_ok=True)
    with open(path / "clients.yaml", "w") as f:
        yaml.safe_dump(clients, f, sort_keys=False)


def emit_views(apps, out_dir):
    # view paths in app specs are relative to the stack root
    stack_root = ROOT.parent
    for app in apps:
        for view in app.get("data", {}).get("views", []):
            src = stack_root / view
            if src.exists():
                dst = out_dir / "plane" / "views" / src.name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(src, dst)


def emit_proxy(instance, apps, out_dir, inst_dir):
    """Emit the Traefik file-provider config (dynamic.yml).

    Routes come from each app's `proxy:` section (hostname + host-published
    port via the docker gateway 172.17.0.1) plus the traefik app's own extra
    `routes:` (e.g. the apex). TLS certs are discovered from the instance tree
    (inst_dir/certs/<name>/{fullchain,privkey}.pem) and mounted by the traefik
    app's `./certs` volume.
    """
    def _route_name(prefix, host):
        # Wildcards must yield unique names — a `*.irl.coop` and a
        # `*.studio.irl.coop` on the same app would otherwise both collapse to
        # `<app>-wildcard` and overwrite each other in the routers dict.
        if host.startswith("*."):
            label = "wildcard-" + host[2:].replace(".", "-")
        else:
            label = host.split(".")[0]
        return f"{prefix}-{label}"

    def _host_rule(host):
        # Traefik v3.5 rejects `Host(`*.domain`)` globs (HostSNI "not a valid
        # hostname"); emit a single-label HostRegexp wildcard instead. Keeps the
        # apex unmatched and blocks multi-label subdomains.
        if host.startswith("*."):
            escaped = host[2:].replace(".", "[.]")
            return f"HostRegexp(`^[^.]+[.]{escaped}$`)"
        return f"Host(`{host}`)"

    routes = []
    for app in apps:
        proxies = app.get("proxy")
        if not proxies:
            continue
        if isinstance(proxies, dict):
            proxies = [proxies]
        for p in proxies:
            host = p["hostname"]
            routes.append(
                (_route_name(app["name"], host), host, p["port"], p.get("priority"))
            )
    for app in apps:
        if app["name"] == "traefik":
            for r in app.get("routes", []):
                host = r["hostname"]
                routes.append(
                    (_route_name("traefik", host), host, r["port"], r.get("priority"))
                )
    http = {"routers": {}, "services": {}}
    for name, host, port, priority in routes:
        router = {"rule": _host_rule(host), "service": name, "tls": {}}
        if priority is not None:
            router["priority"] = priority
        http["routers"][name] = router
        http["services"][name] = {
            "loadBalancer": {"servers": [{"url": f"http://172.17.0.1:{port}"}]}
        }
    # Discover every cert in the instance tree (inst_dir/certs/<name>/{fullchain,
    # privkey}.pem). The traefik app mounts ./certs → /etc/traefik/certs:ro, so
    # each subdir holding a keypair becomes a TLS cert entry; `lego/` (acme.sh
    # state) is skipped because it holds .cer/.key, not fullchain/privkey.pem.
    certificates = []
    certs_root = inst_dir / "certs"
    if certs_root.is_dir():
        for cert_dir in sorted(certs_root.iterdir()):
            if not cert_dir.is_dir():
                continue
            if (cert_dir / "fullchain.pem").exists() and (
                cert_dir / "privkey.pem"
            ).exists():
                certificates.append(
                    {
                        "certFile": f"/etc/traefik/certs/{cert_dir.name}/fullchain.pem",
                        "keyFile": f"/etc/traefik/certs/{cert_dir.name}/privkey.pem",
                    }
                )
    dynamic = {
        "http": http,
        "tls": {"certificates": certificates},
    }
    path = out_dir / "compose" / "proxy"
    path.mkdir(parents=True, exist_ok=True)
    with open(path / "dynamic.yml", "w") as f:
        yaml.safe_dump(dynamic, f, sort_keys=False)


def emit_ansible_edge(instance, inst_dir, out_dir):
    """Emit the edge deploy playbook (cert sync + proxy pillar up)."""
    cert_src = str(inst_dir / "certs")
    playbook = [
        {
            "name": "Deploy edge (traefik)",
            "hosts": "all",
            "become": True,
            "tasks": [
                {
                    "name": "Ensure proxy dirs exist",
                    "ansible.builtin.file": {
                        "path": "/opt/app/proxy",
                        "state": "directory",
                    },
                },
                {
                    "name": "Sync edge compose + dynamic config",
                    "ansible.posix.synchronize": {
                        "src": "../compose/proxy/",
                        "dest": "/opt/app/proxy/",
                        "recursive": True,
                    },
                },
                {
                    "name": "Copy the *.irl.coop wildcard cert",
                    "ansible.builtin.copy": {
                        "src": cert_src + "/",
                        "dest": "/opt/app/proxy/certs/",
                        "mode": "0600",
                    },
                },
                {
                    "name": "Up the edge",
                    "ansible.builtin.shell": "docker compose -f /opt/app/proxy/docker-compose.yml up -d --remove-orphans",
                },
            ],
        }
    ]
    path = out_dir / "ansible" / "playbooks"
    path.mkdir(parents=True, exist_ok=True)
    with open(path / "edge.yml", "w") as f:
        yaml.safe_dump(playbook, f, sort_keys=False)


def emit_secrets_env(instance, inst_dir, master_hex, out_dir):
    """Emit out/<instance>/secrets.env — every ${SECRET:<name>} reference the
    specs use, resolved to derived values, as KEY=name lines. Host-side
    processes (coop-api dev) source this; gitignored with the rest of out/.
    KEY naming: the SECRET name itself (dots stay), UPPER-SNAKE for env use."""
    import re
    used = []
    for app_name in instance["apps"]:
        raw = load(inst_dir / "apps" / f"{app_name}.yaml")
        for m in re.finditer(r"\$\{SECRET:([a-zA-Z0-9._-]+)\}", str(raw)):
            used.append(m.group(1))
    lines = ["# derived-key secrets (HKDF from secrets/master.key) — generated",
             "# source this file into host processes; gitignored with out/"]
    for name in sorted(set(used)):
        key = name.upper().replace(".", "_").replace("-", "_")
        lines.append(f"{key}={derived_secrets.derive(name, master_hex, instance['domain'])}")
    (out_dir / "secrets.env").write_text("\n".join(lines) + "\n")


def emit_matrix_config(inst_dir, out_dir):
    """Copy config/matrix/*.template to out/ — secrets stay as ${SYNAPSE_*} env
    placeholders, rendered by the synapse-s3 entrypoint at runtime (no secret
    ever baked into a generated file)."""
    src_dir = inst_dir / "config" / "matrix"
    if not src_dir.exists():
        return
    dest_dir = out_dir / "config" / "matrix"
    dest_dir.mkdir(parents=True, exist_ok=True)
    for tmpl in src_dir.glob("*.template"):
        shutil.copy(tmpl, dest_dir / tmpl.name[: -len(".template")])


def emit_navigation(apps, stack_root):
    """Emit the dashboard sidebar's external-app links from the declarative tree.

    Apps with a `nav:` block (label/icon/section) and a `proxy:` entry get a
    sidebar link; href = https://<first proxy hostname>. Writes a generated TS
    module into the dashboard source (imported by navigations.ts) so adding an
    app to the tree adds it to the sidebar — no hand-editing. `type: source`
    apps (coop-api) are included since they still carry a proxy hostname.
    """
    nav_apps = []
    for app in apps:
        nav = app.get("nav")
        if not nav:
            continue
        proxies = app.get("proxy")
        if not proxies:
            continue
        if isinstance(proxies, dict):
            proxies = [proxies]
        nav_apps.append(
            {
                "title": nav["label"],
                "href": nav.get("href") or f"https://{proxies[0]['hostname']}",
                "iconName": nav["icon"],
                "section": nav.get("section", "Coop"),
            }
        )
    lines = [
        "// GENERATED by infra/build/generator.py — do not edit; regenerate after",
        "// changing the declarative tree (infra/instances/dev/).",
        'import type { DynamicIconNameType } from "@/types"',
        "",
        "export type GeneratedApp = {",
        "  title: string",
        "  href: string",
        "  iconName: DynamicIconNameType",
        "  section: string",
        "}",
        "",
        "export const generatedApps: GeneratedApp[] = [",
    ]
    for a in nav_apps:
        lines.append(
            '  { title: "%s", href: "%s", iconName: "%s", section: "%s" },'
            % (a["title"], a["href"], a["iconName"], a["section"])
        )
    lines.append("]")
    lines.append("")
    path = stack_root / "apps/web/irl-dashboard/src/data/apps.generated.ts"
    path.write_text("\n".join(lines))


def main():
    if len(sys.argv) < 2:
        print("usage: generator.py <instance>"); sys.exit(1)
    name = sys.argv[1]
    inst_dir = ROOT / "instances" / name
    instance = load(inst_dir / "instance.yaml")
    # Derived-key secrets: one master → every ${SECRET:<name>} reference.
    # The master key must exist (secrets/ensure_master creates it on demand).
    master_hex = derived_secrets.load_master(inst_dir)

    # Tier 2: external secrets (ansible vault). Only decrypt when a spec
    # actually references ${VAULT:<name>} — instances that use derived keys
    # only never need ansible-vault on the generation host.
    needs_vault = any(
        "${VAULT:" in (inst_dir / "apps" / f"{app_name}.yaml").read_text()
        for app_name in instance["apps"]
    )
    vault = (
        derived_secrets.load_vault(
            ROOT / "ansible" / "inventory" / "group_vars" / "all" / "vault.yml",
            inst_dir / "secrets" / "vault-pass",
        )
        if needs_vault
        else {}
    )

    apps = []
    for app_name in instance["apps"]:
        app = load(inst_dir / "apps" / f"{app_name}.yaml")
        app["name"] = app_name
        app = substitute(app, instance["domain"])
        app = derived_secrets.substitute(app, master_hex, instance["domain"])
        app = derived_secrets.substitute_vault(app, vault)
        apps.append(app)

    # `enabled: false` = declared but not wired (no public image / not
    # deployed) — skip compose emission, edge routes, OIDC registry and
    # inventory for those; the spec stays in the tree as the intent record.
    apps = [a for a in apps if a.get("enabled", True) is not False]

    out = ROOT / "out" / name
    if out.exists():
        shutil.rmtree(out)

    by_pillar = {}
    for app in apps:
        if app["type"] == "source":
            continue  # source builds ship their own compose (e.g. Plane)
        if app.get("enabled", True) is False:
            continue  # declared-but-not-wired (no public image / no deploy yet)
        by_pillar.setdefault(app["pillar"], []).append(app)
    for pillar, pillar_apps in by_pillar.items():
        dir_ = out / "compose" / pillar
        dir_.mkdir(parents=True, exist_ok=True)
        emit_compose(pillar_apps, dir_, inst_dir)

    emit_inventory(instance, apps, out)
    emit_clients(instance, apps, out)
    emit_views(apps, out)
    emit_proxy(instance, apps, out, inst_dir)
    emit_ansible_edge(instance, inst_dir, out)
    emit_secrets_env(instance, inst_dir, master_hex, out)
    emit_matrix_config(inst_dir, out)
    emit_navigation(apps, ROOT.parent)

    manifest = out / "MANIFEST.md"
    manifest.write_text(
        f"# Generated for instance `{name}`\n\n"
        f"Apps: {', '.join(a['name'] for a in apps)}\n"
        f"Pillars: {', '.join(sorted(by_pillar))}\n"
        "Generated by infra/build/generator.py — edit the tree, not this.\n"
    )
    print(f"generated {out}")


if __name__ == "__main__":
    main()
