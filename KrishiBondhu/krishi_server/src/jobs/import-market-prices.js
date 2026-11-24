import "../config/env.config.js";

import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import mongoose from "mongoose";
import { connectDatabase, disconnectDatabase } from "../config/database.js";
import { MarketPriceObservation } from "../models/marketpriceobservation.model.js";
import { normalizeMarketGrade } from "../config/marketAlert.config.js";
import { INGESTION_TARGET_DATABASE, assertIngestionTarget } from "../config/ingestionTarget.config.js";

const allowedDivisions = new Set(["Dhaka", "Chattogram", "Khulna", "Rajshahi", "Barishal", "Rangpur", "Sylhet", "Mymensingh", "National"]);
const allowedTypes = new Set(["producer", "wholesale", "retail"]);
const allowedFrequencies = new Set(["daily", "weekly", "monthly"]);
const allowedHosts = new Set(["dam.gov.bd", "www.dam.gov.bd", "market.dam.gov.bd", "data.mendeley.com", "objectstorage.ap-dcc-gazipur-1.oraclecloud15.com"]);

export function cleanMarketPriceImportRow(row, index = 0) {
  const commodity = typeof row?.commodity === "string" ? row.commodity.trim().slice(0, 80) : "";
  const division = typeof row?.division === "string" ? row.division.trim() : "";
  const priceType = row?.priceType;
  const unit = typeof row?.unit === "string" ? row.unit.trim().slice(0, 24) : "";
  const source = typeof row?.source === "string" ? row.source.trim().slice(0, 160) : "";
  const sourceUrl = typeof row?.sourceUrl === "string" ? row.sourceUrl.trim() : "";
  const dateText = typeof row?.date === "string" ? row.date : "";
  const observedOn = /^\d{4}-\d{2}-\d{2}$/.test(dateText) ? new Date(`${dateText}T00:00:00.000Z`) : null;
  const priceMin = Number(row?.priceMin);
  const priceMax = Number(row?.priceMax);
  const frequency = typeof row?.frequency === "string" ? row.frequency.trim().toLowerCase() : "daily";
  let sourceHost = "";
  try { sourceHost = new URL(sourceUrl).hostname.toLowerCase(); } catch {}
  if (!commodity || !allowedDivisions.has(division) || !allowedTypes.has(priceType) || !allowedFrequencies.has(frequency) || !unit || !source || !allowedHosts.has(sourceHost) || !observedOn || Number.isNaN(observedOn.getTime()) || observedOn.toISOString().slice(0, 10) !== dateText || !Number.isFinite(priceMin) || !Number.isFinite(priceMax) || priceMin <= 0 || priceMax < priceMin) {
    throw new Error(`Invalid market record at row ${index + 1}; see the market data format in science/README.md.`);
  }
  return {
    commodity, commodityKey: commodity.toLocaleLowerCase("en"), division,
    district: typeof row.district === "string" ? row.district.trim().slice(0, 60) : "",
    upazila: typeof row.upazila === "string" ? row.upazila.trim().slice(0, 60) : "",
    market: typeof row.market === "string" ? row.market.trim().slice(0, 120) : "",
    frequency, priceType, unit, priceMin, priceMax, observedOn, source, sourceUrl,
    grade: normalizeMarketGrade(row?.grade),
    licence: typeof row.licence === "string" ? row.licence.trim().slice(0, 120) : "",
    qualityStatus: row.qualityStatus === "verified" ? "verified" : "review",
  };
}

export function marketPriceImportIdentity(record) {
  return {
    commodityKey: record.commodityKey,
    division: record.division,
    district: record.district,
    upazila: record.upazila,
    market: record.market,
    frequency: record.frequency,
    priceType: record.priceType,
    unit: record.unit,
    observedOn: record.observedOn,
    source: record.source,
    grade: record.grade,
  };
}

export function deduplicateMarketPriceImportRows(records) {
  const unique = new Map();
  for (const record of records) {
    const key = JSON.stringify(marketPriceImportIdentity(record));
    const prior = unique.get(key);
    if (prior && (prior.priceMin !== record.priceMin || prior.priceMax !== record.priceMax || prior.sourceUrl !== record.sourceUrl || prior.licence !== record.licence || prior.qualityStatus !== record.qualityStatus)) {
      throw new Error("Conflicting duplicate market observations found; resolve source rows before import.");
    }
    if (!prior) unique.set(key, record);
  }
  return [...unique.values()];
}

async function main() {
  const inputPath = process.argv[2];
  if (!inputPath) throw new Error("Usage: npm run import:market-prices -- <normalized-json-file>");
  const absolutePath = path.resolve(process.cwd(), inputPath);
  const document = JSON.parse(await fs.readFile(absolutePath, "utf8"));
  const rows = Array.isArray(document) ? document : document?.observations;
  if (!Array.isArray(rows) || rows.length === 0) throw new Error("Input must be a non-empty JSON array or { observations: [...] }.");
  const records = deduplicateMarketPriceImportRows(rows.map(cleanMarketPriceImportRow));
  if (!process.env.MONGODB_URI || process.env.MONGODB_TEST_URI) {
    throw new Error("Market import requires MONGODB_URI and refuses test-database overrides.");
  }
  await connectDatabase({ required: true, databaseName: INGESTION_TARGET_DATABASE });
  assertIngestionTarget(mongoose.connection);
  await MarketPriceObservation.createIndexes();
  const identityIndex = (await MarketPriceObservation.collection.indexes()).find(
    (index) => index.name === "market_observation_location_frequency_source_grade_unique"
  );
  if (!identityIndex?.unique) throw new Error("Market observation identity index is unavailable; refusing import.");
  const importedSources = [...new Set(records.map((record) => record.source))];
  const countBefore = await MarketPriceObservation.countDocuments({ source: { $in: importedSources } });
  const operations = records.map((record) => ({
    updateOne: {
      filter: marketPriceImportIdentity(record),
      update: { $setOnInsert: record }, upsert: true,
    },
  }));
  for (let start = 0; start < operations.length; start += 500) {
    await MarketPriceObservation.bulkWrite(operations.slice(start, start + 500), { ordered: false });
  }
  const countAfter = await MarketPriceObservation.countDocuments({ source: { $in: importedSources } });
  const inserted = Math.max(0, countAfter - countBefore);
  console.log(`[market-import] input=${records.length} sourceRecordsBefore=${countBefore} sourceRecordsAfter=${countAfter} countIncrease=${inserted}; insert-only writes preserve existing records and review-only observations remain excluded from verified quote APIs`);
}

const isMain = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  main().catch((error) => { console.error(`[market-import] ${error.message}`); process.exitCode = 1; }).finally(disconnectDatabase);
}
