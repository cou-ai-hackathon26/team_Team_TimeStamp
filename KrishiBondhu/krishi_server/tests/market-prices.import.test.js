import test from "node:test";
import assert from "node:assert/strict";
import {
  cleanMarketPriceImportRow,
  deduplicateMarketPriceImportRows,
  marketPriceImportIdentity,
} from "../src/jobs/import-market-prices.js";

const sourceRow = {
  commodity: "Green chilli",
  division: "National",
  district: "",
  upazila: "",
  market: "",
  date: "2024-01-20",
  frequency: "daily",
  priceType: "retail",
  unit: "BDT/kg",
  priceMin: 200,
  priceMax: 220,
  source: "AgriPriceBD: Daily Bangladesh market price digitization",
  sourceUrl: "https://data.mendeley.com/datasets/bkmxnrn3hn/1",
  licence: "CC BY 4.0; cite the AgriPriceBD dataset",
  qualityStatus: "review",
};

test("market importer preserves source frequency, provenance, and review quality", () => {
  const record = cleanMarketPriceImportRow(sourceRow);
  assert.equal(record.frequency, "daily");
  assert.equal(record.division, "National");
  assert.equal(record.qualityStatus, "review");
  assert.equal(record.sourceUrl, sourceRow.sourceUrl);
  assert.equal(record.licence, sourceRow.licence);
  assert.equal(record.observedOn.toISOString(), "2024-01-20T00:00:00.000Z");
});

test("market importer rejects invalid dates, prices, frequencies, and unapproved hosts", () => {
  for (const patch of [
    { date: "2024-02-31" },
    { priceMin: 0 },
    { priceMax: 190 },
    { frequency: "hourly" },
    { sourceUrl: "https://example.invalid/data" },
  ]) {
    assert.throws(() => cleanMarketPriceImportRow({ ...sourceRow, ...patch }));
  }
});

test("market import identity includes full location, frequency, source, and grade", () => {
  const record = cleanMarketPriceImportRow({ ...sourceRow, district: "Cumilla", upazila: "Burichang", market: "Sadar", grade: "Grade A" });
  assert.deepEqual(marketPriceImportIdentity(record), {
    commodityKey: "green chilli",
    division: "National",
    district: "Cumilla",
    upazila: "Burichang",
    market: "Sadar",
    frequency: "daily",
    priceType: "retail",
    unit: "BDT/kg",
    observedOn: new Date("2024-01-20T00:00:00.000Z"),
    source: sourceRow.source,
    grade: "grade a",
  });
});

test("exact duplicates collapse and conflicting duplicates fail closed", () => {
  const first = cleanMarketPriceImportRow(sourceRow);
  const same = cleanMarketPriceImportRow(sourceRow);
  const conflict = cleanMarketPriceImportRow({ ...sourceRow, priceMax: 225 });
  assert.equal(deduplicateMarketPriceImportRows([first, same]).length, 1);
  assert.throws(() => deduplicateMarketPriceImportRows([first, conflict]), /Conflicting duplicate/);
});
