const { chromium } = require("playwright");
const path = require("path");
const BASE = "http://localhost:3000";
const OUT = path.resolve("browser-evidence");
const user = { id: "u1", name: "Test Farmer", email: "farmer@example.com", role: "farmer", phone: "+8801712345678", phoneVerifiedAt: "2026-11-20T10:00:00Z", preferredDistrict: "cumilla" };
const prefs = { categories: { weather: { enabled: true, subscribedAt: null, unsubscribedAt: null }, market: { enabled: false, subscribedAt: null, unsubscribedAt: null }, farmReminder: { enabled: false, subscribedAt: null, unsubscribedAt: null } }, consent: { givenAt: "2026-11-20T10:00:00Z", source: "settings", revokedAt: null }, phone: { verified: true, last4: "5678" } };

async function route(page) {
  await page.route("**/api/v1/**", (r) => {
    const url = r.request().url();
    if (url.includes("/auth/me")) return r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, data: { user } }) });
    if (url.includes("/sms-subscriptions")) return r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, data: prefs }) });
    if (url.includes("/districts")) return r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, data: { districts: [{ code: "cumilla", nameEn: "Cumilla", nameBn: "কুমিল্লা" }] } }) });
    return r.fulfill({ status: 200, contentType: "application/json", body: "{}" });
  });
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  for (const [name, viewport] of [["desktop", { width: 1366, height: 900 }], ["mobile", { width: 390, height: 844 }]]) {
    const page = await browser.newPage({ viewport });
    await route(page);
    await page.goto(`${BASE}/settings`, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForSelector("#sms-alerts-heading", { timeout: 30000 });
    await page.waitForTimeout(1800);
    await page.screenshot({ path: path.join(OUT, `qa-settings-${name}.png`), fullPage: true });
    console.log(name, JSON.stringify(await page.evaluate(() => ({
      noFly: document.querySelectorAll("[data-bondhu-no-fly]").length,
      switches: document.querySelectorAll('[role="switch"]').length,
      scrollWidth: document.documentElement.scrollWidth,
      viewport: window.innerWidth,
    }))));
    await page.close();
  }
  await browser.close();
})();
