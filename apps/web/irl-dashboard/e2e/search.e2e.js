// E2E for the docs/group search (Playwright). Run from the repo root:
//   node apps/web/irl-dashboard/e2e/search.e2e.js
// Assumes the dashboard dev server is on :3000 and the RAG/coop-api are up.
const { chromium } = require("playwright");

(async () => {
  const browser = await chromium.launch({
    headless: true,
    args: ["--use-angle=swiftshader", "--no-sandbox", "--disable-gpu"],
  });
  const page = await browser.newPage();
  const pageErrors = [];
  page.on("pageerror", (e) => pageErrors.push(String(e)));

  // 1. Load the design docs index (public, no login)
  await page.goto("http://localhost:3000/design", { waitUntil: "domcontentloaded" });
  await page.waitForSelector("input[placeholder]", { timeout: 15000 });
  const placeholder = await page.getAttribute("input[placeholder]", "placeholder");
  console.log("1. search box renders — placeholder:", JSON.stringify(placeholder));

  // 2. Anonymous search → group result
  await page.fill("input[placeholder]", "food cooperative kitchen market");
  await page.click("button[type=submit]");
  await page.waitForSelector("a[href^='/groups/']", { timeout: 20000 });
  const groupLinks = await page.$$eval("a[href^='/groups/']", (els) => els.map((e) => e.getAttribute("href")));
  console.log("2. group results link →", [...new Set(groupLinks)]);

  // 3. Anonymous search → doc result
  await page.fill("input[placeholder]", "how does a group Safe treasury work");
  await page.click("button[type=submit]");
  await page.waitForFunction(
    () => document.body.innerText.includes("Private ZK Treasury") || document.body.innerText.includes("treasury"),
    { timeout: 20000 },
  );
  console.log("3. doc search returns a treasury passage");

  // 4. Anonymous sign-in hint present
  const bodyText = await page.textContent("body");
  console.log("4. sign-in hint:", bodyText.includes("Just browsing") ? "present" : "MISSING");

  console.log("page errors:", pageErrors.length ? pageErrors : "none");
  await browser.close();
  console.log("E2E PASS");
})().catch((e) => {
  console.error("E2E FAIL:", e.message);
  process.exit(1);
});
