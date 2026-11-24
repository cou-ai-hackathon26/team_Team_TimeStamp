import test from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { getCropList, getResearchPhenology } from "../src/controllers/cropcalendar.controller.js";
import { createApp } from "../src/app.js";

async function invoke(handler, query = {}) {
  let statusCode = 200;
  let body;
  const res = {
    status(code) { statusCode = code; return this; },
    json(value) { body = value; return this; },
  };
  await handler({ query }, res, (error) => { throw error; });
  return { statusCode, body };
}

test("licensed AgriClimateBD phenology API identifies research data and paginates", async () => {
  const first = await invoke(getResearchPhenology, { page: "1", limit: "2" });
  assert.equal(first.statusCode, 200);
  assert.equal(first.body.success, true);
  assert.equal(first.body.data.pagination.totalRecords, 4692);
  assert.equal(first.body.data.records.length, 2);
  assert.equal(first.body.data.source.datasetId, "10.17632/tb5x9gw2pt.2");
  assert.equal(first.body.data.source.license, "CC BY 4.0");
  assert.equal(first.body.data.source.isOfficialRecommendation, false);
  assert.equal(first.body.data.sources.length, 2);
  assert.deepEqual(first.body.data.sources.map((source) => source.datasetId).sort(), [
    "10.17632/8pvfs5wyzf.5",
    "10.17632/tb5x9gw2pt.2",
  ]);
  assert.equal(first.body.meta.isOfficialRecommendation, false);
  assert.ok(first.body.data.records[0].periods);
  assert.ok(first.body.data.records[0].qualityFlags);
  assert.equal("Seasonal_Rainfall_total_mm" in first.body.data.records[0], false);
});

test("national source adds licensed phenology without implying district coverage", async () => {
  const all = await invoke(getResearchPhenology, { page: "10", limit: "500" });
  const national = all.body.data.records.filter((record) => record.sourceId === "10.17632/8pvfs5wyzf.5");
  assert.equal(national.length, 86);
  assert.equal(national[0].district, null);
  assert.equal(national[0].geographicLevel, "national");
  assert.equal(national[0].isOfficialRecommendation, false);
  assert.equal(national[0].license, "CC BY 4.0");

  const districtFiltered = await invoke(getResearchPhenology, { district: "Cumilla", limit: "500" });
  assert.equal(districtFiltered.body.data.records.some((record) => record.sourceId === "10.17632/8pvfs5wyzf.5"), false);
  assert.equal(districtFiltered.body.data.pagination.totalRecords, 72);
});

test("district, crop, and season filters are exact case-insensitive matches", async () => {
  const result = await invoke(getResearchPhenology, {
    district: "cumilla",
    crop: "aman",
    season: "kharif 2",
    limit: "10",
  });
  assert.equal(result.statusCode, 200);
  assert.equal(result.body.data.pagination.totalRecords, 1);
  const record = result.body.data.records[0];
  assert.equal(record.district, "Cumilla");
  assert.equal(record.cropName, "Aman");
  assert.equal(record.season, "Kharif 2");
});

test("invalid, repeated, and unsupported research query parameters are rejected", async () => {
  for (const query of [
    { page: "0" },
    { limit: "501" },
    { district: ["Cumilla", "Chattogram"] },
    { crop: "x".repeat(101) },
    { ownerId: "untrusted" },
  ]) {
    const result = await invoke(getResearchPhenology, query);
    assert.equal(result.statusCode, 400, JSON.stringify(query));
    assert.equal(result.body.error.code, "VALIDATION_ERROR");
  }
});

test("research integration does not alter official crop calendar coverage", async () => {
  const result = await invoke(getCropList);
  assert.equal(result.statusCode, 200);
  assert.equal(result.body.data.length, 4);
  assert.deepEqual(
    result.body.data.map((crop) => crop.cropId).sort(),
    ["aus_rice", "boro_rice", "monsoon_aman", "mustard"]
  );
});

test("public HTTP research endpoint returns licensed, filtered records without MongoDB", async () => {
  const server = http.createServer(createApp());
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  try {
    const base = `http://127.0.0.1:${server.address().port}/api/v1/crop-calendar/research-phenology`;
    const response = await fetch(`${base}?district=Chattogram&crop=Aman&season=Kharif%202&limit=5`);
    assert.equal(response.status, 200);
    const body = await response.json();
    assert.equal(body.success, true);
    assert.equal(body.data.pagination.totalRecords, 1);
    assert.equal(body.data.records[0].district, "Chattogram");
    assert.equal(body.data.source.license, "CC BY 4.0");
    assert.equal(body.data.records[0].sourceId, "10.17632/tb5x9gw2pt.2");
    assert.equal(body.meta.isOfficialRecommendation, false);
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});
