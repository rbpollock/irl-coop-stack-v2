// ---------------------------------------------------------------------------
// Canonical group slug — the {slug}.irl.coop host key AND the group's stable,
// human-addressable name. Single source of truth for slugification + the
// reserved-subdomain set, shared by group creation (groups.ts) and anywhere
// else a host → group resolution happens.
// ---------------------------------------------------------------------------

// Infrastructure / routing subdomains a group must never squat. These are the
// live edge routes (see infra/out/dev/compose/proxy/dynamic.yml) plus reserved
// platform names — if a group took "api" or "mail" it would shadow the stack.
export const RESERVED_SLUGS = new Set<string>([
  "www", "app", "api", "auth", "login", "signin", "signup", "register", "logout",
  "mail", "smtp", "imap", "pop", "mta-sts", "_dmarc", "webmail",
  "nocodb", "plane", "s3", "s3api", "events", "forms", "studio",
  "matrix", "element", "call", "postiz", "docs", "admin", "status",
  "dashboard", "portal", "help", "support", "billing",
  "irl", "coop", "root", "god", "system", "internal", "localhost",
]);

// Name → canonical slug: lowercase, strip diacritics (NFKD), collapse runs of
// non-alphanumerics to a single hyphen, trim edges, cap at 63 chars (DNS label
// limit). Empty string when the name has no alphanumerics at all.
export function slugify(name: string): string {
  return (name ?? "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 63)
    .replace(/-$/g, "");
}

// An explicitly-requested slug must already be canonical and non-reserved.
export function isValidSlug(slug: string): boolean {
  return /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(slug) && !RESERVED_SLUGS.has(slug);
}
