// Cooperation Starter Pack: prove the template reaches the gallery, the new coop
// categories render and filter, and "Use this template" creates a real survey.
import { chromium } from "playwright";

const BASE = "https://forms.irl.coop";
const TITLE = "Is cooperation for you?";

const browser = await chromium.launch({ args: ["--no-sandbox"] });
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });

// 1) coop session (same-origin login on api.irl.coop sets the .irl.coop cookie)
await page.goto("https://api.irl.coop/api/auth/config", { waitUntil: "domcontentloaded", timeout: 60000 });
const login = await page.evaluate(async () => {
  const r = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: "e2e-test@irl.coop", password: "E2e-ERPNext-2026!" }),
  });
  return r.status;
});
console.log("coop login:", login);

// 2) through the gate: enter via the app root (this is where gate-SSO fires and the
// session cookie is minted), then deep-link to the gallery.
const wsArg = process.argv[2] ?? null;
await page.goto(`${BASE}/`, { waitUntil: "networkidle", timeout: 60000 });
await page.waitForTimeout(4000);
console.log("after root:", page.url());
await page.goto(`${BASE}/workspaces/${wsArg}/surveys/templates`, {
  waitUntil: "networkidle",
  timeout: 60000,
});
await page.waitForTimeout(3500);
let url = page.url();
console.log("workspaceId:", wsArg);

const gallery = await page.evaluate((title) => {
  const text = document.body.innerText;
  const tiles = [...document.querySelectorAll("button")].filter(
    (b) => b.querySelector("h3")?.textContent?.trim() === title
  ).length;
  return {
    hasTitle: text.includes(title),
    tiles,
    hasCooperativeCategory: text.includes("Cooperative"),
    hasGroupOrganizerCategory: text.includes("Group organizer"),
    url: location.href,
  };
}, TITLE);
console.log("gallery:", JSON.stringify(gallery));
await page.screenshot({ path: "/tmp/fb-templates-gallery.png", fullPage: true });

// 3) the new coop category actually filters (click "Cooperative", tile must survive)
const filterCheck = await page.evaluate((title) => {
  const btn = [...document.querySelectorAll("button")].find(
    (b) => b.textContent?.trim() === "Cooperative"
  );
  if (!btn) return { clicked: false };
  btn.click();
  return { clicked: true };
}, TITLE);
await page.waitForTimeout(2500);
const afterFilter = await page.evaluate((title) => {
  const tiles = [...document.querySelectorAll("button")].filter(
    (b) => b.querySelector("h3")?.textContent?.trim() === title
  ).length;
  return { tiles };
}, TITLE);
console.log("cooperative filter:", JSON.stringify({ ...filterCheck, ...afterFilter }));

// 4) the featured row on the surveys home must lead with the pack
await page.goto(`${BASE}/workspaces/${wsArg}/surveys`, { waitUntil: "networkidle", timeout: 60000 });
await page.waitForTimeout(4500);
const featured = await page.evaluate((title) => {
  const text = document.body.innerText;
  return { hasTitle: text.includes(title), url: location.href };
}, TITLE);
console.log("featured row:", JSON.stringify(featured));
await page.screenshot({ path: "/tmp/fb-featured-row.png", fullPage: true });

// 5) "Use this template" creates a real survey
await page.goto(`${BASE}/workspaces/${wsArg}/surveys/templates`, {
  waitUntil: "networkidle",
  timeout: 60000,
});
await page.waitForTimeout(3000);
let created = null;
await page.evaluate((title) => {
  const tile = [...document.querySelectorAll("button")].find(
    (b) => b.querySelector("h3")?.textContent?.trim() === title
  );
  tile?.click();
}, TITLE);
await page.waitForTimeout(1500);
const useClicked = await page.evaluate(() => {
  const b = [...document.querySelectorAll("button")].find((el) =>
    /use this template/i.test(el.getAttribute("aria-label") ?? el.textContent ?? "")
  );
  if (b) {
    b.click();
    return true;
  }
  return false;
});
await page.waitForTimeout(6000);
created = page.url();
console.log("clicked use-template:", useClicked, "| after create:", created);

console.log("RESULT", JSON.stringify({ gallery, afterFilter, featured, createdSurveyUrl: created }));
await browser.close();
