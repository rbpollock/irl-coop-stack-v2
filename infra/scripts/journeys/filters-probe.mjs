// Print the actual filter button labels the app renders in the templates gallery.
import { chromium } from "playwright";

const BASE = "https://forms.irl.coop";
const ws = process.argv[2];

const browser = await chromium.launch({ args: ["--no-sandbox"] });
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });

await page.goto("https://api.irl.coop/api/auth/config", { waitUntil: "domcontentloaded", timeout: 60000 });
console.log(
  "login:",
  await page.evaluate(async () => {
    const r = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: "e2e-test@irl.coop", password: "E2e-ERPNext-2026!" }),
    });
    return r.status;
  })
);

await page.goto(`${BASE}/`, { waitUntil: "networkidle", timeout: 60000 });
await page.waitForTimeout(3000);
await page.goto(`${BASE}/workspaces/${ws}/surveys/templates`, { waitUntil: "networkidle", timeout: 60000 });
await page.waitForTimeout(4000);

// TemplateFilters renders its buttons with border-slate-800 — that's the filter row.
const filters = await page.evaluate(() => {
  const btns = [...document.querySelectorAll("button")].filter((b) =>
    (b.className || "").includes("border-slate-800")
  );
  return btns.map((b) => b.textContent.trim());
});
console.log("FILTER LABELS:", JSON.stringify(filters, null, 0));

// also: which chunk hash the page loaded (so we can compare with a cached browser)
const chunk = await page.evaluate(() =>
  [...document.querySelectorAll("script[src]")].map((s) => s.getAttribute("src")).filter((s) => s && s.includes("/_next/")).slice(0, 3)
);
console.log("CHUNKS:", JSON.stringify(chunk));
await browser.close();
