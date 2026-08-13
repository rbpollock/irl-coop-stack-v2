#!/usr/bin/env python3
"""Configure Keycloak WebAuthn Passwordless for the irl-coop realm.

Creates the WebAuthn Passwordless flow (username form -> WebAuthn passwordless
authenticator), makes it the realm's browser flow, and sets the passwordless
RP policy (rpId auth.irl.coop). The Google kc_idp_hint path is unaffected
(the hint redirects before any form). Idempotent.
"""
import hashlib
import hmac as hm
import json
import urllib.error
import urllib.parse
import urllib.request

FLOW_ALIAS = "webauthn-passwordless"

master = open("/home/service/development/irl-coop-stack-v2/infra/instances/dev/secrets/master.key").read().strip()


def derive(name):
    prk = hm.new(b"irl.coop", bytes.fromhex(master), "sha256").digest()
    out, t, c = b"", b"", 1
    while len(out) < 32:
        t = hm.new(prk, t + f"irlcoop/{name}".encode() + bytes([c]), "sha256").digest()
        out += t
        c += 1
    return out[:32].hex()


def post_form(url, fields):
    req = urllib.request.Request(url, method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"},
                                 data=urllib.parse.urlencode(fields).encode())
    try:
        r = urllib.request.urlopen(req, timeout=20)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, (json.loads(raw) if raw else {})


def api(method, url, tok, body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": f"Bearer {tok}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(url, method=method, headers=headers, data=data)
    try:
        resp = urllib.request.urlopen(r, timeout=20)
        raw = resp.read()
        return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, (json.loads(raw) if raw else None)


def main():
    st, b = post_form("http://localhost:8081/realms/master/protocol/openid-connect/token",
                      {"grant_type": "password", "client_id": "admin-cli", "username": "admin",
                       "password": derive("keycloak.admin")})
    at = b["access_token"]
    AB = "http://localhost:8081/admin/realms/irl-coop"

    # 1. the flow (idempotent: delete any stale one first)
    s, flows = api("GET", f"{AB}/authentication/flows", at)
    for f in flows:
        if f.get("alias") == FLOW_ALIAS and not f.get("builtIn"):
            api("DELETE", f"{AB}/authentication/flows/{f['id']}", at)
    s, _ = api("POST", f"{AB}/authentication/flows", at,
               {"alias": FLOW_ALIAS, "providerId": "basic-flow",
                "description": "irl.coop passkey login (WebAuthn passwordless)", "topLevel": True})
    print("flow created:", s)

    # 2. the executions: username form, then the WebAuthn passwordless step
    for provider in ("auth-username-form", "webauthn-authenticator-passwordless"):
        s, _ = api("POST", f"{AB}/authentication/flows/{FLOW_ALIAS}/executions/execution", at,
                   {"provider": provider})
        print(f"execution {provider}:", s)

    # 3. set the webauthn execution to REQUIRED
    s, execs = api("GET", f"{AB}/authentication/flows/{FLOW_ALIAS}/executions", at)
    for ex in execs:
        if ex.get("providerId") == "webauthn-authenticator-passwordless":
            s, _ = api("PUT", f"{AB}/authentication/flows/{FLOW_ALIAS}/executions", at,
                       {"id": ex["id"], "requirement": "REQUIRED",
                        "displayName": ex.get("displayName"), "alias": ex.get("alias"),
                        "providerId": ex.get("providerId"), "authenticationFlow": ex.get("authenticationFlow")})
            print("webauthn execution -> REQUIRED:", s)

    # 4. make it the realm's browser flow
    s, realm = api("GET", f"{AB}", at)
    realm["browserFlow"] = FLOW_ALIAS
    s, _ = api("PUT", f"{AB}", at, realm)
    print("browserFlow set:", s)

    # 5. the passwordless RP policy (rpId = the Keycloak host)
    s, realm = api("GET", f"{AB}", at)
    realm["webAuthnPolicyPasswordlessRpEntityName"] = "irl.coop"
    realm["webAuthnPolicyPasswordlessRpId"] = "auth.irl.coop"
    realm["webAuthnPolicyPasswordlessSignatureAlgorithms"] = ["ES256"]
    s, _ = api("PUT", f"{AB}", at, realm)
    print("passwordless policy set:", s)

    # verify
    s, realm = api("GET", f"{AB}", at)
    print("browserFlow now:", realm.get("browserFlow"))
    print("rpId now:", realm.get("webAuthnPolicyPasswordlessRpId"))
    s, flows = api("GET", f"{AB}/authentication/flows", at)
    for f in flows:
        if f.get("alias") == FLOW_ALIAS:
            s, execs = api("GET", f"{AB}/authentication/flows/{FLOW_ALIAS}/executions", at)
            print("executions:", [(e.get("providerId"), e.get("requirement")) for e in execs])


if __name__ == "__main__":
    main()
