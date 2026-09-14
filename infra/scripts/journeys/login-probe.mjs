// Does the native login page actually offer the coop SSO door — and does clicking it
// land the member inside the app?
import { chromium } from "playwright";

const BASE = "https://forms.irl.coop";
const browser = await chromium.launch({ args: ["--no-sandbox"] });
const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });

await page.goto("https://api.irl.coop/api/auth/config", { waitUntil: "domcontentloaded", timeout: 60000 });
console.log(
  "coop login:",
  await page.evaluate(async () => {
    const r = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: "e2e-test@irl.coop", password: "E2e-ERPNext-2026!" }),
    });
    return r.status;
  })
);

// the native login page (client-rendered form)
await page.goto(`${BASE}/auth/login`, { waitUntil: "networkidle", timeout: 60000 });
await page.waitForTimeout(4000);

const probe = await page.evaluate(() => {
  const a = [...document.querySelectorAll("a")].find((el) =>
    /sign in with irl\.coop/i.test(el.textContent || "")
  );
  return {
    url: location.href,
    hasDoor: !!a,
    href: a ? a.getAttribute("href") : null,
    title: document.title,
  };
});
console.log("login page:", JSON.stringify(probe));
await page.screenshot({ path: "/tmp/fb-login-door.png", fullPage: true });

if (probe.hasDoor) {
  await Promise.all([
    page.waitForURL((u) => !/\/auth\/login/.test(u.toString()), { timeout: 60000 }).catch(() => null),
    page.evaluate(() => {
      const a = [...document.querySelectorAll("a")].find((el) =>
        /sign in with irl\.coop/i.test(el.textContent || "")
      );
      a?.click();
    }),
  ]);
  await page.waitForTimeout(4000);
  console.log("after click:", page.url());
  await page.screenshot({ path: "/tmp/fb-login-door-after.png", fullPage: true });
}
await browser.close();
