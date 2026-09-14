// Throwaway: screenshot a URL with the container's playwright chromium.
import { chromium } from "playwright";

const [url, out] = process.argv.slice(2);
const browser = await chromium.launch({ args: ["--no-sandbox"] });
const ctx = await browser.newContext({ viewport: { width: 880, height: 1000 }, deviceScaleFactor: 2 });
const page = await ctx.newPage();
await page.goto(url, { waitUntil: "networkidle", timeout: 60000 });
await page.waitForTimeout(2500);
await page.screenshot({ path: out, fullPage: true });
const text = await page.evaluate(() => document.body.innerText.replace(/\s+/g, " ").slice(0, 260));
const styles = await page.evaluate(() => {
  const btns = [...document.querySelectorAll("button")];
  const next = btns.find((b) => /next/i.test(b.textContent || "")) || btns[0];
  const cs = next ? getComputedStyle(next) : null;
  const body = getComputedStyle(document.body);
  const leaves = [...document.querySelectorAll("p,span,strong,b,h2")]
    .filter((el) => el.getClientRects().length > 0 && (el.textContent || "").trim().length > 12);
  const sample = leaves.length ? getComputedStyle(leaves[Math.floor(leaves.length / 2)]) : null;
  const headlineEl = [...document.querySelectorAll("h1,h2,h3,h4")].find(
    (el) => el.getClientRects().length > 0
  );
  return {
    buttonBg: cs?.backgroundColor,
    buttonRadius: cs?.borderRadius,
    buttonText: cs?.color,
    sampleTextColor: sample?.color,
    font: cs?.fontFamily?.slice(0, 40),
    bodyFont: body.fontFamily.slice(0, 40),
    headlineFont: headlineEl ? getComputedStyle(headlineEl).fontFamily.slice(0, 44) : null,
    fontLoaded: document.fonts ? [...document.fonts].some((f) => /Cormorant/i.test(f.family)) : null,
    brandLinks: [...document.querySelectorAll("a")]
      .map((a) => a.href)
      .filter((h) => /irl\.coop|formbricks\.com/.test(h)),
  };
});
console.log("SHOT", out, "| title:", await page.title());
console.log("TEXT:", text);
console.log("STYLES:", JSON.stringify(styles));
await browser.close();
