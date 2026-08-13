#!/usr/bin/env python3
"""Configure Keycloak WebAuthn passwordless for the irl-coop realm (25.0.6).

Recipe (all the quirks learned the hard way — do not "simplify"):
  1. The realm's browser flow = `browser-passkey`, a COPY of the built-in
     browser flow (preserves the cookie/redirector/forms/OTP structure).
  2. A FLAT `webauthn-authenticator-passwordless` execution (ALTERNATIVE)
     raised to the top of the flow — NO conditional subflow, NO condition.
     Why: the conditional-user-configured condition calls the webauthn's
     configuredFor with a null user on the login-page GET and NPEs in EVERY
     Keycloak version (24.0.4 → 26). The flat execution works because the
     25+ authenticate() has the ID-less null-user guard: it sets the
     challenge attributes and lets the form's challenge render the page.
  3. The passwordless RP policy: rpId auth.irl.coop, ES256.
  4. Enrollment: set the `webauthn-register-passwordless` required action on
     a user; their first password login shows the registration ceremony.
  The google kc_idp_hint path is preserved (the copied flow's redirector).
Idempotent.
"""
import hmac as hm
import json
import urllib.error
import urllib.parse
import urllib.request

NEW_FLOW = "browser-passkey"

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
        return e.code, (json.loads(raw) if raw else {})


def main():
    st, b = post_form("http://localhost:8081/realms/master/protocol/openid-connect/token",
                      {"grant_type": "password", "client_id": "admin-cli", "username": "admin",
                       "password": derive("keycloak.admin")})
    at = b["access_token"]
    AB = "http://localhost:8081/admin/realms/irl-coop"

    # 1. fresh copy of the built-in browser flow
    s, realm = api("GET", f"{AB}", at)
    realm["browserFlow"] = "browser"
    api("PUT", f"{AB}", at, realm)
    s, flows = api("GET", f"{AB}/authentication/flows", at)
    for f in flows:
        if f.get("alias") == NEW_FLOW and not f.get("builtIn"):
            api("DELETE", f"{AB}/authentication/flows/{f['id']}", at)
    api("POST", f"{AB}/authentication/flows/browser/copy", at, {"newName": NEW_FLOW})

    # 2. flat webauthn execution (ALTERNATIVE), raised to the top
    api("POST", f"{AB}/authentication/flows/{NEW_FLOW}/executions/execution", at,
        {"provider": "webauthn-authenticator-passwordless"})
    s, execs = api("GET", f"{AB}/authentication/flows/{NEW_FLOW}/executions", at)
    for ex in execs:
        if ex.get("providerId") == "webauthn-authenticator-passwordless" and not ex.get("authenticationFlow"):
            api("PUT", f"{AB}/authentication/flows/{NEW_FLOW}/executions", at,
                {"id": ex["id"], "requirement": "ALTERNATIVE", "displayName": ex.get("displayName"),
                 "alias": ex.get("alias"), "providerId": ex.get("providerId"),
                 "authenticationFlow": ex.get("authenticationFlow")})
            for _ in range(4):
                s2, _ = api("POST", f"{AB}/authentication/flows/{NEW_FLOW}/executions/{ex['id']}/raise", at)
                if s2 == 404:
                    break

    # 3. passwordless RP policy
    s, realm = api("GET", f"{AB}", at)
    realm["webAuthnPolicyPasswordlessRpEntityName"] = "irl.coop"
    realm["webAuthnPolicyPasswordlessRpId"] = "auth.irl.coop"
    realm["webAuthnPolicyPasswordlessSignatureAlgorithms"] = ["ES256"]
    api("PUT", f"{AB}", at, realm)

    # 4. wire it as the browser flow + report
    s, realm = api("GET", f"{AB}", at)
    realm["browserFlow"] = NEW_FLOW
    api("PUT", f"{AB}", at, realm)
    print("browserFlow ->", NEW_FLOW)
    s, execs = api("GET", f"{AB}/authentication/flows/{NEW_FLOW}/executions", at)
    for e in execs:
        pid = e.get("providerId") or e.get("displayName")
        print("  ", pid, e.get("requirement"))


if __name__ == "__main__":
    main()
