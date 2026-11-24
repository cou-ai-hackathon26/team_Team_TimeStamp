import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const dataPath = path.resolve(__dirname, "../../data/crops/agriclimatedbd_research_phenology.json");
const nationalDataPath = path.resolve(__dirname, "../../data/crops/bangladesh_agricultural_datasets_v5_phenology.json");
let cachedData;

function loadData() {
  if (!cachedData) {
    const data = JSON.parse(fs.readFileSync(dataPath, "utf8"));
    const national = JSON.parse(fs.readFileSync(nationalDataPath, "utf8"));
    if (data?.metadata?.datasetId !== "10.17632/tb5x9gw2pt.2" || !Array.isArray(data.metadata.records)
      || national?.metadata?.datasetId !== "10.17632/8pvfs5wyzf.5" || !Array.isArray(national.metadata.records)) {
      throw new Error("Licensed research crop-phenology reference is invalid.");
    }
    cachedData = { district: data.metadata, national: national.metadata };
  }
  return cachedData;
}

export function listResearchPhenology({ district, crop, season, page = 1, limit = 100 } = {}) {
  const datasets = loadData();
  const districtSource = datasets.district;
  const records = [
    ...districtSource.records.map((record) => ({
      ...record,
      sourceId: districtSource.datasetId,
      sourceTitle: districtSource.title,
      sourceUrl: districtSource.sourceUrl,
      license: districtSource.license,
      attribution: districtSource.attribution,
      evidenceType: districtSource.phenologyEvidence,
      geographicLevel: districtSource.geographicLevel,
      isOfficialRecommendation: false,
    })),
    // This second source is national only. A district-filtered response must
    // never imply that its nationwide periods are district-specific.
    ...(district ? [] : datasets.national.records),
  ];
  const matches = records.filter((record) =>
    (!district || (record.district && record.district.toLocaleLowerCase("en") === district.toLocaleLowerCase("en")))
    && (!crop || record.cropName.toLocaleLowerCase("en") === crop.toLocaleLowerCase("en"))
    && (!season || record.season.toLocaleLowerCase("en") === season.toLocaleLowerCase("en"))
  );
  const start = (page - 1) * limit;
  const source = districtSource;
  return {
    records: matches.slice(start, start + limit),
    pagination: {
      page,
      limit,
      totalRecords: matches.length,
      totalPages: Math.ceil(matches.length / limit),
    },
    source: {
      title: source.title,
      datasetId: source.datasetId,
      datasetVersion: source.datasetVersion,
      sourceUrl: source.sourceUrl,
      publishedDate: source.publishedDate,
      retrievedDate: source.retrievedDate,
      license: source.license,
      attribution: source.attribution,
      dataType: source.dataType,
      evidenceType: "survey-derived research period summaries",
      geographicLevel: source.geographicLevel,
      periodGranularity: source.periodGranularity,
      isOfficialRecommendation: false,
      observationPeriod: source.observationPeriod,
      qualityLimitations: source.qualityLimitations,
      audit: source.audit,
      includesMultipleDatasets: true,
    },
    sources: [districtSource, datasets.national].map((item) => ({
      title: item.title,
      datasetId: item.datasetId,
      datasetVersion: item.datasetVersion,
      sourceUrl: item.sourceUrl,
      publishedDate: item.publishedDate,
      retrievedDate: item.retrievedDate,
      license: item.license,
      attribution: item.attribution,
      dataType: item.dataType,
      evidenceType: item.evidenceType || item.phenologyEvidence,
      geographicLevel: item.geographicLevel,
      periodGranularity: item.periodGranularity,
      isOfficialRecommendation: false,
      observationPeriod: item.observationPeriod,
      qualityLimitations: item.qualityLimitations,
      audit: item.audit,
    })),
  };
}
