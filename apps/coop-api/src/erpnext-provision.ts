// ERPNext (accounting.irl.coop) personal-tenant provisioning — Phase 1.
//
// Every sign-in converges here, idempotently (design:
// docs/design/erpnext-tenancy-notifications.md §3):
//   1. ERPNext User exists (SSO-created or created here) with first_name +
//      user_type System User.
//   2. Roles include `Accounts User` (the self-accounting floor role).
//   3. Personal Company "<Full Name> — personal" exists (US, Standard CoA),
//      seeded Warehouse Type masters on first site.
//   4. User Permission (allow: <personal Company>) scopes the user to their
//      own books — they never see the whole company list.
//
// Best-effort, like the other provisioners: failures are logged and swallowed
// — sign-in must never break because ERPNext is down; the next sign-in retries.
// Driven by the Coop Sync integration identity (ERPNEXT_SYNC_USER/PASSWORD),
// never the platform superuser.
const ERP_BASE = process.env.ERPNEXT_URL ?? "";
const ERP_USER = process.env.ERPNEXT_SYNC_USER ?? "";
const ERP_PASSWORD = process.env.ERPNEXT_SYNC_PASSWORD ?? "";
const ENABLED = !!(ERP_BASE && ERP_USER && ERP_PASSWORD);

const WAREHOUSE_TYPES = [
  "Transit", "Stores", "Raw Materials", "Finished Goods",
  "Work In Progress", "Scrap", "Rejected", "Packaging",
] as const;

const TIMEOUT_MS = 15_000;

type Json = Record<string, any>;

async function erpFetch(path: string, init: RequestInit = {}): Promise<Response> {
  return fetch(`${ERP_BASE}${path}`, {
    ...init,
    headers: { ...(init.headers ?? {}) },
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
}

// Open a Coop Sync session; returns the `sid=…` cookie value or null.
async function erpLogin(): Promise<string | null> {
  const body = new URLSearchParams({ usr: ERP_USER, pwd: ERP_PASSWORD });
  const resp = await erpFetch("/api/method/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!resp.ok) return null;
  const setCookie = resp.headers.get("set-cookie") ?? "";
  const sid = setCookie.split(";")[0];
  return sid || null;
}

async function erpApi(path: string, sid: string, init: RequestInit = {}): Promise<{ status: number; json: Json | null }> {
  const resp = await erpFetch(path, {
    ...init,
    headers: { Cookie: sid, ...(init.headers ?? {}) },
  });
  let json: Json | null = null;
  try {
    json = (await resp.json()) as Json;
  } catch {
    /* non-JSON (nginx 301/HTML etc.) */
  }
  return { status: resp.status, json };
}

function enc(s: string): string {
  return encodeURIComponent(s);
}

function firstFive(name: string): string {
  const clean = (name || "").replace(/[^a-zA-Z0-9]/g, "");
  return clean.slice(0, 5).toUpperCase() || "MEMBER";
}

// Create missing Warehouse Type masters (fresh-site REST gap: Company creation
// needs them; each needs an explicit `name`).
async function ensureWarehouseTypes(sid: string): Promise<void> {
  for (const t of WAREHOUSE_TYPES) {
    await erpApi(`/api/resource/Warehouse%20Type/${enc(t)}`, sid).catch(() => null);
    await erpApi(`/api/resource/Warehouse%20Type`, sid, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: t, warehouse_type_name: t }),
    });
  }
}

async function createCompany(sid: string, companyName: string, abbr: string): Promise<boolean> {
  // Company creation can fail once per missing Warehouse Type on a fresh site.
  for (let attempt = 0; attempt < 3; attempt++) {
    const res = await erpApi(`/api/resource/Company`, sid, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        company_name: companyName,
        abbr,
        default_currency: "USD",
        country: "United States",
        chart_of_accounts: "Standard",
      }),
    });
    if (res.status === 200) return true;
    const msg = JSON.stringify(res.json ?? "");
    const missing = /Could not find Warehouse Type: ([A-Za-z ]+)/.exec(msg)?.[1];
    if (missing) {
      await erpApi(`/api/resource/Warehouse%20Type`, sid, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: missing, warehouse_type_name: missing }),
      });
      continue;
    }
    if (res.status === 409 || /already exists/i.test(msg)) return true; // raced — fine
    console.error(`[erp-provision] Company create failed: ${res.status} ${msg.slice(0, 200)}`);
    return false;
  }
  return false;
}

async function ensureUserPermission(sid: string, userEmail: string, companyName: string): Promise<void> {
  const list = await erpApi(
    `/api/resource/User%20Permission?filters=${enc(JSON.stringify([["user", "=", userEmail], ["allow", "=", "Company"], ["for_value", "=", companyName]]))}&limit_page_length=1`,
    sid,
  );
  const has = (list.json?.data as Json[] | undefined)?.length ?? 0;
  if (has) return;
  await erpApi(`/api/resource/User%20Permission`, sid, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user: userEmail, allow: "Company", for_value: companyName }),
  });
}

async function ensureUser(sid: string, email: string, fullName: string): Promise<string | null> {
  const firstName = (fullName || "").trim().split(/\s+/)[0] || email.split("@")[0];
  const existing = await erpApi(`/api/resource/User/${enc(email)}`, sid);
  if (existing.status === 200) {
    const roles = (existing.json?.data?.roles as Json[] | undefined) ?? [];
    if (!roles.some((r: Json) => r.role === "Accounts User")) {
      const merged = [...roles, { role: "Accounts User" }];
      await erpApi(`/api/resource/User/${enc(email)}`, sid, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ roles: merged, user_type: "System User" }),
      });
    }
    return firstName;
  }
  // SSO will create the user at their first ERPNext login anyway; creating it
  // here means the Company + permission exist before they ever arrive.
  const created = await erpApi(`/api/resource/User`, sid, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email,
      first_name: firstName,
      enabled: 1,
      user_type: "System User",
      send_welcome_email: 0,
      roles: [{ role: "Accounts User" }],
    }),
  });
  if (created.status !== 200) {
    console.error(`[erp-provision] User create failed: ${created.status} ${JSON.stringify(created.json ?? "").slice(0, 200)}`);
    return null;
  }
  return firstName;
}

export async function ensureErpPersonalTenancy(email: string | null | undefined, fullName: string | null | undefined): Promise<void> {
  if (!ENABLED) return;
  if (!email) return;
  try {
    const sid = await erpLogin();
    if (!sid) {
      console.error("[erp-provision] Coop Sync login failed");
      return;
    }
    await ensureWarehouseTypes(sid);
    const firstName = await ensureUser(sid, email, fullName ?? "");
    if (!firstName) return;
    const companyName = `${fullName?.trim() || firstName} — personal`;
    const abbr = firstFive(firstName);
    const company = await erpApi(`/api/resource/Company/${enc(companyName)}`, sid);
    if (company.status !== 200) {
      await createCompany(sid, companyName, abbr);
    }
    await ensureUserPermission(sid, email, companyName);
  } catch (err) {
    console.error(`[erp-provision] failed for ${(email ?? "").slice(0, 40)}: ${(err as Error).message}`);
  }
}
