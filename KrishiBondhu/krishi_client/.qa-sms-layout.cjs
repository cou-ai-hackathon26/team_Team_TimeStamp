const { chromium } = require("playwright");
const path = require("path");
const OUT = path.resolve("browser-evidence");
const USER = { id: "u1", name: "Test Farmer", email: "farmer@example.com", role: "farmer", phoneVerifiedAt: "2026-11-20T10:00:00Z" };
const prefs = () => ({
  categories: { weather: { enabled: true }, market: { enabled: false }, farmReminder: { enabled: false } },
  consent: { givenAt: "2026-11-20T10:00:00Z", source: "settings", revokedAt: null },
  phone: { verified: true, last4: "5678" },
});
async function mock(page) {
  await page.route("**/api/v1/**", async (r) => {
    const u = r.request().url();
    const send = (s, d) => r.fulfill({ status: s, contentType: "application/json", body: JSON.stringify({ success: s < 400, data: d }) });
    if (u.includes("/auth/me")) return send(200, { user: USER });
    if (u.includes("/sms-subscriptions")) return send(200, prefs());
    if (u.includes("/districts")) return send(200, { districts: [] });
    if (u.includes("/data-sources")) return send(200, []);
    if (u.includes("/prices/catalog")) return send(200, { series: [] });
    return send(200, {});
  });
}
(async () => {
  const b = await chromium.launch({ headless: true });
  const report = {};
  for (const width of [390, 768, 1024, 1440, 1920]) {
    const p = await b.newPage({ viewport: { width, height: 1000 } });
    await mock(p);
    await p.goto("http://localhost:3000/settings#sms-alerts-heading", { waitUntil: "domcontentloaded", timeout: 60000 });
    await p.waitForTimeout(3000);
    report[width] = await p.evaluate(() => {
      const heading = [...document.querySelectorAll("p")].find((el) => /How your SMS alert travels/.test(el.textContent));
      const card = heading?.closest("div");
      const items = card ? [...card.querySelectorAll("ol > li")] : [];
      return {
        columns: new Set(items.map((li) => Math.round(li.getBoundingClientRect().left))).size,
        cardWidths: items.map((li) => Math.round(li.getBoundingClientRect().width)),
        textHeights: items.map((li) => Math.round(li.querySelector("p")?.getBoundingClientRect().height || 0)),
        overflow: document.documentElement.scrollWidth > window.innerWidth,
        sectionWidth: card ? Math.round(card.getBoundingClientRect().width) : 0,
      };
    });
    await p.screenshot({ path: path.join(OUT, `sms-settings-responsive-${width}.png`), fullPage: false });
    await p.close();
  }
  console.log(JSON.stringify(report, null, 2));
  await b.close();
})();
