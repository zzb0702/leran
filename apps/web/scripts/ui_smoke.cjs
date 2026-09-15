/* UI smoke: login → today → library → workbench */
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright-core");

const candidates = [
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
];

async function main() {
  let browser;
  for (const p of candidates) {
    if (!fs.existsSync(p)) continue;
    try {
      browser = await chromium.launch({ headless: true, executablePath: p });
      console.log("LAUNCHED", p);
      break;
    } catch (e) {
      console.log("fail", p, e.message);
    }
  }
  if (!browser) {
    console.error("NO_BROWSER");
    process.exit(2);
  }

  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await page.goto("http://127.0.0.1:5173/login", { waitUntil: "domcontentloaded", timeout: 20000 });
  console.log("TITLE", await page.title());
  console.log("BRAND", await page.getByText("Leran", { exact: true }).first().isVisible());

  await page.fill('input[type="email"]', "demo@leran.local");
  await page.fill('input[type="password"]', "demo1234");
  await page.click('button[type="submit"]');
  await page.waitForURL("http://127.0.0.1:5173/", { timeout: 15000 });
  console.log("AFTER_LOGIN", page.url());
  console.log("TODAY", await page.getByText("待复习").isVisible());

  await page.click('a[href="/library"]');
  await page.waitForTimeout(800);
  console.log("LIBRARY", await page.getByText("GPU Throughput").first().isVisible());

  await page.getByText("GPU Throughput").first().click();
  await page.waitForTimeout(1200);
  console.log("EXPORT_BTN", await page.getByText("导出双语 SRT").isVisible());
  const segs = await page.locator(".seg-row").count();
  console.log("SEGS", segs);

  // click a word chip and mine if present
  const chip = page.locator(".word-chip").first();
  if (await chip.count()) {
    await chip.click();
    await page.getByRole("button", { name: "入卡" }).click();
    await page.waitForTimeout(400);
    console.log("MINED", await page.getByText(/已入卡/).isVisible().catch(() => false));
  }

  await page.screenshot({ path: path.join(__dirname, "..", "..", "data", "ui-workbench.png") });
  await page.click('a[href="/review"]');
  await page.waitForTimeout(600);
  const reviewVisible = await page.getByText("复习").first().isVisible();
  console.log("REVIEW", reviewVisible);
  await page.screenshot({ path: path.join(__dirname, "..", "..", "data", "ui-review.png") });

  await browser.close();
  console.log("UI_OK");
}

main().catch((e) => {
  console.error("UI_FAIL", e);
  process.exit(1);
});
