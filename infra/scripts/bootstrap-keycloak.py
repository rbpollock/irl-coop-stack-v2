#!/usr/bin/env python3
"""Bootstrap the irl-coop Keycloak realm from scratch."""
import json, hmac as hm, sys, time
import urllib.request, urllib.error, urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MASTER = ROOT / "instances/dev/secrets/master.key"
CLIENTS_YAML = ROOT / "out/dev/keycloak/clients.yaml"
KC_URL = "http://172.17.0.1:8081"
REALM = "irl-coop"

def fail(msg): print(f"ERROR: {msg}", file=sys.stderr); sys.exit(1)
def say(msg): print(f"  {msg}")

def derive(name):
    if not MASTER.exists(): fail(f"master.key missing: {MASTER}")
    master = MASTER.read_text().strip()
    prk = hm.new(b"irl.coop", bytes.fromhex(master), "sha256").digest()
    out, t, c = b"", b"", 1
    while len(out) < 32:
        t = hm.new(prk, t + f"irlcoop/{name}".encode() + bytes([c]), "sha256").digest()
        out += t; c += 1
    return out[:32].hex()

def request(method, url, headers=None, body=None, ignore=None):
    data = json.dumps(body).encode() if body is not None else None
    h = headers or {}
    if body is not None: h.setdefault("Content-Type", "application/json")
    r = urllib.request.Request(url, method=method, headers=h, data=data)
    try:
        resp = urllib.request.urlopen(r, timeout=20)
        raw = resp.read()
        return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read()
        if ignore and e.code in ignore:
            return e.code, (json.loads(raw) if raw else None)
        err = json.loads(raw) if raw else {}
        msg = err.get("errorMessage", err.get("error", str(e)))
        fail(f"{method} {url} -> {e.code}: {msg}")

def post_form(url, fields):
    r = urllib.request.Request(url, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=urllib.parse.urlencode(fields).encode())
    try:
        resp = urllib.request.urlopen(r, timeout=20)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        fail(f"POST {url} -> {e.code}: {e.read().decode()[:200]}")

# ── 1. Wait ─────────────────────────────────────────────────────────────────
print("=== 1. Waiting for Keycloak ===")
for i in range(30):
    try:
        c, _ = request("GET", f"{KC_URL}/realms/master")
        if c == 200: say("ready"); break
    except Exception:
        pass
    time.sleep(2)
    if i == 29: fail("timeout")

# ── 2. Auth ─────────────────────────────────────────────────────────────────
print("=== 2. Authenticating ===")
_, tok = post_form(f"{KC_URL}/realms/master/protocol/openid-connect/token", {
    "grant_type": "password", "client_id": "admin-cli",
    "username": "admin", "password": derive("keycloak.admin")})
token = tok["access_token"]
auth = {"Authorization": f"Bearer {token}"}

def api(method, path, body=None, ignore=None):
    return request(method, f"{KC_URL}/admin/realms/{REALM}{path}", headers=auth, body=body, ignore=ignore)

# ── 3. Create realm ─────────────────────────────────────────────────────────
print("=== 3. Realm ===")
c, _ = api("GET", "", ignore=[404])
if c == 404:
    request("POST", f"{KC_URL}/admin/realms", headers=auth, body={
        "realm": REALM, "enabled": True, "displayName": "irl.coop",
        "sslRequired": "external", "registrationAllowed": False,
        "loginWithEmailAllowed": True, "internationalizationEnabled": False})
    say("created")
else:
    say("already exists")

# ── 4. Clients ──────────────────────────────────────────────────────────────
print("=== 4. Clients ===")
import yaml
clients = yaml.safe_load(CLIENTS_YAML.read_text()) if CLIENTS_YAML.exists() else {}
by_id = {}
for cid, spec in clients.items():
    by_id[cid] = {
        "clientId": cid, "secret": derive(f"keycloak.{cid}")[:64],
        "redirectUris": spec.get("redirect_uris", []),
        "publicClient": spec.get("public", False)}
by_id.setdefault("web-app", {
    "clientId": "web-app", "secret": derive("keycloak.web-app")[:64],
    "redirectUris": ["https://irl.coop/api/auth/callback/keycloak",
                     "https://hermes.irl.coop/api/auth/callback/keycloak"],
    "publicClient": True})

def upsert(cid, cfg):
    c, existing = api("GET", f"/clients?clientId={urllib.parse.quote(cid)}&maxResults=1")
    payload = {"clientId": cid, "enabled": True, "redirectUris": cfg["redirectUris"],
               "publicClient": cfg.get("publicClient", False), "protocol": "openid-connect",
               "directAccessGrantsEnabled": True, "standardFlowEnabled": True,
               "implicitFlowEnabled": False}
    if not cfg.get("publicClient", False):
        payload.update({"clientAuthenticatorType": "client-secret", "secret": cfg["secret"],
                        "serviceAccountsEnabled": True})
    if existing:
        api("PUT", f"/clients/{existing[0]['id']}", payload)
        say(f"{cid}: updated")
        return existing[0]["id"]
    else:
        api("POST", "/clients", payload)
        _, created = api("GET", f"/clients?clientId={urllib.parse.quote(cid)}&maxResults=1")
        say(f"{cid}: created")
        return created[0]["id"]

for cid, cfg in by_id.items():
    upsert(cid, cfg)

# ── 5. Service account roles ────────────────────────────────────────────────
print("=== 5. coop-api roles ===")
_, cc = api("GET", "/clients?clientId=coop-api&maxResults=1")
if not cc: fail("coop-api missing")
coop_uuid = cc[0]["id"]
_, sa = api("GET", f"/clients/{coop_uuid}/service-account-user")
sa_id = sa["id"]
_, rm_clients = api("GET", "/clients?clientId=realm-management")
rm_uuid = next((c["id"] for c in rm_clients if c.get("clientId") == "realm-management"), None)
if not rm_uuid: fail("realm-management client missing")
_, roles = api("GET", f"/clients/{rm_uuid}/roles")
role_obj = next((r for r in roles if r.get("name") == "manage-users"), None)
if not role_obj: fail("manage-users role missing")
api("POST", f"/users/{sa_id}/role-mappings/clients/{rm_uuid}",
    [{"id": role_obj["id"], "name": "manage-users"}], ignore=[409])
say("manage-users granted")

# ── 6. Browser passkey flow ─────────────────────────────────────────────────
print("=== 6. WebAuthn flow ===")
NEW_FLOW = "browser-passkey"
_, realm = api("GET", "")
realm["browserFlow"] = "browser"
api("PUT", "", realm)
_, flows = api("GET", "/authentication/flows")
for f in flows:
    if f.get("alias") == NEW_FLOW and not f.get("builtIn"):
        api("DELETE", f"/authentication/flows/{f['id']}")
        say("deleted old flow")
api("POST", "/authentication/flows/browser/copy", {"newName": NEW_FLOW})
say("copied browser flow")
api("POST", f"/authentication/flows/{NEW_FLOW}/executions/execution",
    {"provider": "webauthn-authenticator-passwordless"})
_, execs = api("GET", f"/authentication/flows/{NEW_FLOW}/executions")
for ex in execs:
    if ex.get("providerId") == "webauthn-authenticator-passwordless" and not ex.get("authenticationFlow"):
        api("PUT", f"/authentication/flows/{NEW_FLOW}/executions", {
            "id": ex["id"], "requirement": "ALTERNATIVE",
            "displayName": ex.get("displayName"), "alias": ex.get("alias"),
            "providerId": ex.get("providerId"), "authenticationFlow": ex.get("authenticationFlow")})
        for _ in range(10):
            s2, _ = api("POST", f"/authentication/flows/{NEW_FLOW}/executions/{ex['id']}/raise", None, ignore=[404])
            if s2 == 404: break
        say("raised webauthn to top")

# ── 7. RP policy ────────────────────────────────────────────────────────────
print("=== 7. RP policy ===")
_, realm = api("GET", "")
realm["webAuthnPolicyPasswordlessRpEntityName"] = "irl.coop"
realm["webAuthnPolicyPasswordlessRpId"] = "auth.irl.coop"
realm["webAuthnPolicyPasswordlessSignatureAlgorithms"] = ["ES256"]
api("PUT", "", realm)
say("auth.irl.coop / ES256")

# ── 8. Activate ─────────────────────────────────────────────────────────────
print("=== 8. Activate ===")
_, realm = api("GET", "")
realm["browserFlow"] = NEW_FLOW
api("PUT", "", realm)
say("browserFlow -> browser-passkey")

# Report
print("\n=== OK ===")
print(f"Realm: {REALM}  Issuer: {KC_URL}/realms/{REALM}  Flow: {NEW_FLOW}")
print(f"Clients: {', '.join(by_id.keys())}")
