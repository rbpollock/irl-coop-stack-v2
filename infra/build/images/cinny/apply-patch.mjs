import { readFileSync, writeFileSync } from "fs";

const p = "src/app/pages/auth/SSOLogin.tsx";
let s = readFileSync(p, "utf8");

// 1. import useEffect
s = s.replace(
  "import React, { useMemo } from 'react';",
  "import React, { useEffect, useMemo } from 'react';",
);

// 2. auto-redirect to the first SSO provider once the login page mounts
const anchor =
  "  const getSSOIdUrl = (ssoId?: string): string =>\n    mx.getSsoLoginUrl(redirectUrl, 'sso', ssoId, action);";
const effect =
  anchor +
  "\n\n" +
  "  // irl.coop: auto-login — if SSO is available, immediately redirect to the\n" +
  "  // first provider. Keycloak completes silently when the member already has a\n" +
  "  // coop session (logged into the dashboard), so Cinny logs in with no click.\n" +
  "  useEffect(() => {\n" +
  "    // don't auto-redirect while an SSO callback (loginToken) is pending —\n" +
  "    // let the login page consume it, otherwise this loops back to SSO.\n" +
  "    if (new URLSearchParams(window.location.search).get('loginToken')) return;\n" +
  "    const first = providers?.[0];\n" +
  "    if (first?.id) window.location.href = getSSOIdUrl(first.id);\n" +
  "    // eslint-disable-next-line react-hooks/exhaustive-deps\n" +
  "  }, [providers, redirectUrl, action]);";

if (!s.includes(anchor)) throw new Error("SSOLogin anchor not found");
s = s.replace(anchor, effect);
writeFileSync(p, s);
console.log("patched SSOLogin.tsx for auto-login");
