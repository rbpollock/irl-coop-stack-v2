// Chrome check: mint a coop session, walk the gate into Formbricks, screenshot
// the app chrome and read a few computed styles.
import { chromium } from "playwright";

const OUT = process.argv[2] ?? "/tmp/fb-chrome.png";
const browser = await chromium.launch({ args: ["--no-sandbox"] });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
const page = await ctx.newPage();

// 1) coop session (same-origin login on api.irl.coop)
await page.goto("https://api.irl.coop/api/auth/config", { waitUntil: "domcontentloaded" });
const login = await page.evaluate(async () => {
  const r = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: "e2e-test@irl.coop", password: "E2e-ERPNext-2026!" }),
  });
  return r.status;
});
console.log("coop login:", login);

// 2) through the gate into the app (gate-sso auto-login → app home)
await page.goto("https://forms.irl.coop/workspaces", { waitUntil: "networkidle", timeout: 60000 });
await page.waitForTimeout(4000);
if (/404|not found/i.test(await page.evaluate(() => document.body.innerText.slice(0, 120)))) {
  await page.goto("https://forms.irl.coop/", { waitUntil: "networkidle", timeout: 60000 });
  await page.waitForTimeout(4000);
}
console.log("URL:", page.url());

// 3) chrome styles + brand words
const probe = await page.evaluate(() => {
  const root = document.documentElement;
  const rs = getComputedStyle(root);
  const html = root.innerHTML;
  const filled = [...document.querySelectorAll("button,a[class*=bg-],div[class*=bg-]")]
    .filter((el) => el.getClientRects().length > 0)
    .map((el) => getComputedStyle(el).backgroundColor)
    .filter((c) => c && c !== "rgba(0, 0, 0, 0)" && c !== "rgb(255, 255, 255)");
  return {
    text: document.body.innerText.replace(/\s+/g, " ").slice(0, 160),
    url: location.pathname,
    cssVarBrand: rs.getPropertyValue("--color-brand").trim(),
    cssVarFormbricksBrand: rs.getPropertyValue("--formbricks-brand").trim(),
    purpleInDom: (html.match(/#7C3AED/gi) || []).length,
    tealInDom: (html.match(/#00C4B8|#01E0C6|#00DDD0|#00FFE1/gi) || []).length,
    distinctFilledColors: [...new Set(filled)].slice(0, 6),
    hasSidebar: !!document.querySelector("nav,aside,[class*=sidebar],[data-testid*=sidebar]"),
  };
});
console.log("PROBE:", JSON.stringify(probe));
await page.screenshot({ path: OUT, fullPage: false });
console.log("SHOT", OUT);
await browser.close();
