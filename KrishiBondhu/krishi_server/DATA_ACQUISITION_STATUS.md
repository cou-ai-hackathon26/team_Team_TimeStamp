# KrishiBondhu Data Acquisition Status

Updated: 2026-11-24 (Asia/Dhaka)

This report records only verified data loads and source access findings. It does
not treat user listings, estimates, forecasts, satellite retrievals, or cached
values as observed market transactions or field measurements.

## Completed in this acquisition

| Dataset | Source and type | Acquired coverage | Quality and provenance | Storage / refresh |
|---|---|---|---|---|
| NASA POWER daily point agroclimatology | NASA POWER Daily API, API v2.10.5; gridded point estimates, historical/NRT (not local station observations) | Chattogram and Cumilla configured points; 2026-01-01 through 2026-11-20; six parameters: corrected precipitation, mean/max/min temperature, relative humidity, and shortwave radiation | 1,944 observations per district (324 dates × 6 parameters). Per district, 1,940 values passed quality checks; four shortwave-radiation sentinel values (Nov 17–20) remain explicitly `missing_sentinel`, not zero. API time standard is LST, not Bangladesh civil time. | Inserted through the existing guarded NASA ingestion pipeline into `krishi_mama.nasaobservations`; append/provenance history is in `dataingestionlogs`. Run IDs: `run_1795497265277_93b2d5` (Chattogram), `run_1795497315601_daa4d7` (Cumilla). Existing climate latest API returned these records after insertion. |
| NASA GPM IMERG Final half-hourly precipitation | NASA GES DISC / CMR; `GPM_3IMERGHH`, V07 / granule `07B`, Final run, 0.1° grid | Cumilla and Chattogram; Bangladesh local dates 2024-01-01 and 2024-01-02 (the only dates present before this acquisition) | 96 unique half-hour intervals per district across the two days; all 192 district observations are valid. Half-hour rate is `mm/hr`; interval amount is rate × 0.5 in `mm`. Grid coordinates and exact UTC bounds are stored. Both daily totals are complete and valid at 0 mm for each district/date; zero came from valid source intervals, not from missing-value substitution. | 92 previously missing granules fetched via authenticated OPeNDAP and 184 new district records inserted into `krishi_mama.gpmobservations`; original 8 records preserved. `createdAt`, ingestion run ID, granule ID, NASA CMR update time, source response SHA-256, product/version, and UTC standard are retained. All four existing daily API requests returned HTTP 200 and complete 48/48 summaries. |
| Bangladesh historical agricultural prices | AgriPriceBD v1, digitized from Bangladesh DAM daily market-monitoring PDF reports; CC BY 4.0, DOI `10.17632/bkmxnrn3hn.1` | Five products, National-only geography; 2020-07-22 through 2025-06-04; daily retail and wholesale price ranges in BDT/kg | 17,746 structurally valid source observations; 44 invalid price values had already been excluded by the local pipeline and remain missing (never zero-filled). There are no duplicate identities. Publisher says source PDF prices were digitized with an LLM-assisted process; all imported rows therefore remain `review`, not verified. Missing district/market detail is preserved as national-only. | Imported insert-only into `krishi_mama.marketpriceobservations`; collection was empty before import. Source URL, versioned DOI, CC BY 4.0 attribution, observation date, frequency, type, unit, and created timestamp retained. The existing quote-history API correctly returns no verified quote for these rows; it must not be treated as a live price or forecast input until human review/verification. |

The database was queried read-only before the two writes. It contained zero
matching records for either district in the requested 2026 range. No earlier
records were modified. The API's latest usable radiation observation is
2026-11-16, while the other five parameters reach 2026-11-20; consumers must
continue to respect each parameter's observation date.

For GPM, the verified database contained only 8 valid pilot intervals: 3 for
each district on Jan 1 and 1 for each district on Jan 2. The continuation job
filled exactly those gaps, retaining insert-only semantics. After acquisition,
both dates for each district have 48 unique, contiguous, valid intervals. The
existing `/api/v1/precipitation/daily` endpoint independently returned
`complete`, `observedIntervals: 48`, `validIntervals: 48`, and the source total
for all four district/date combinations. This is only a two-day historical
coverage slice; it is not continuous rainfall history for 2024 or later years.
Source documentation: [NASA GPM IMERG Final V07](https://disc.gsfc.nasa.gov/datasets/GPM_3IMERGH_07/summary).

The validated request used the existing configured point coordinates and six
approved parameters. Source documentation: [NASA POWER Daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/).
The existing ingestion cutoff now tracks four UTC days before today, matching
the observed near-real-time delay. Run the existing controlled command with an
explicit date range to refresh data; no unattended scheduler was added.

## Existing local data reused; no duplicate acquisition

- Historical NASA POWER snapshots already cover 2001–2025. They are local
  artifacts; this run did not duplicate or rewrite them, and this run did not
  backfill those snapshots into MongoDB.
- AgriPriceBD was already present in the validated local science pipeline and
  was integrated to MongoDB as review-only historical observations; no duplicate
  archive was downloaded. It is not a current DAM quote. The World Bank RTFP
  history already exists in the separate monthly reference pipeline and API; it
  is modeled/estimated and was not copied into the observed-price collection.
- Existing crop knowledge, the four official crop calendars, weather cache,
  and satellite pilot artifacts were left unchanged.

## Pending or blocked acquisition

| Gap | Source / access | Status and next step |
|---|---|---|
| Authentic current and historical local market observations | [DAM daily market reports](https://market.dam.gov.bd/market_daily_price_report/?L=E) | No documented public machine-readable API contract was identified. Use the existing admin evidence/PDF review and import workflow. For automation, obtain DAM authorization or a supported structured feed first. Do not scrape its CSRF form. |
| Official warnings and station weather | [Bangladesh Meteorological Department](https://www.bmd.gov.bd/web/en/) | API integration requires institutional access/approval. Request API credentials and permitted use from BMD; do not use guessed endpoints. |
| More crop calendars and current district advisories | [BAMIS portal](https://www.bamis.gov.bd/en/page/about-bamis-portal/) | Only four calendars are currently in the project. Public advisory pages exist, but a stable authorized feed and reuse terms have not been established. Request/download official bulk data and reuse terms before automated ingestion. |
| Expanded national crop calendar and advisory guidance | [BBS Yearbook of Agricultural Statistics 2022](https://objectstorage.ap-dcc-gazipur-1.oraclecloud15.com/n/axvjbnqprylg/b/V2Ministry/o/office-bbs/2024/12/85216bc379fa443e837ffac3052a45dc.pdf); [BAMIS crop-weather calendars](https://www.bamis.gov.bd/en/calendar/) | Reviewed publicly readable BBS sowing/transplanting/harvest tables and BAMIS regional calendars. No dataset-level reuse licence was found for these BBS/BAMIS documents; BAMIS pages reserve rights. No records were copied into the application. Request written reuse permission or a machine-readable open-licensed release from BBS/DAE. |
| Bangladesh crop-season research dataset | [Mendeley Data, Bangladesh Agricultural Datasets v1](https://data.mendeley.com/datasets/8pvfs5wyzf/1), DOI `10.17632/8pvfs5wyzf.1`, CC BY 4.0 | Metadata confirms crop transplanting/harvest/temperature fields for 104 crops, derived from Yearbook of Agricultural Statistics Bangladesh 2020 and a crop-seasons article. Dataset API metadata request returned HTTP 401 because Mendeley requires OAuth2; no files were downloaded or imported. The page's Download All action or an authorized Mendeley API client is required. This is secondary research data, not a government-endorsed advisory, and its description does not establish Cumilla/Chattogram geography. |
| Soil fertility and recommendations | [SRDI](https://srdi.gov.bd/) and [BARC Fertilizer Recommendation Guide 2024](https://apps.barc.gov.bd/fertilizer_recommendation/FRG%20English%2030.10.2024.pdf) | Public maps/guidance are not field-specific lab observations. Confirm reuse terms and request machine-readable GIS/lab data from SRDI before importing. |
| Recent satellite soil moisture | [NASA SMAP data](https://nsidc.org/data/smap/data) | Existing local pilot is sparse and dated Jan 2024. Obtain Earthdata access/approved retrieval method, then apply QA and spatial matching before updating; never interpret it as root-zone or field-sensor moisture. |
| Crop yield/area validation | [BBS Yearbook of Agricultural Statistics](https://bbs.portal.gov.bd/site/page/3e838eb6-30a2-4709-be85-40484b0c16c6/%E0%A6%95%E0%A7%83%E0%A6%B7%E0%A6%BF-%E0%A6%AA%E0%A6%B0%E0%A6%BF%E0%A6%B8%E0%A6%82%E0%A6%96%E0%A7%8D%E0%A6%AF%E0%A6%BE%E0%A6%A8-%E0%A6%AC%E0%A6%B0%E0%A7%8D%E0%A6%B7%E0%A6%97%E0%A7%8D%E0%A6%B0%E0%A6%A8%E0%A7%8D%E0%A6%A5) | Official aggregate reports are available, but an authoritative API/bulk structured dataset and reuse terms need confirmation. Use report-level aggregate data only after method, year, crop definition, and geography are mapped. |
| Crop disease labeled data | [BRRI rice insect guidance](https://riceprofile.brri.gov.bd/cultivation/insect) and [BRRI disease guidance](https://riceprofile.brri.gov.bd/index.php/cultivation/disease) | Source-linked guidance exists; no validated local image/diagnosis training dataset was identified. Request licensed, labeled DAE/BRRI data; do not train or claim diagnostic coverage without it. |

## Validation and safety policy

- Preserve source-native type: observed, modeled estimate, forecast, static
  guidance, satellite retrieval, and cache remain separate.
- Store source key, source URL/provider, observation date, ingestion run/time,
  unit, location, quality/sentinel status, and source time standard.
- Keep missing or sentinel values missing; never convert them to zero or use
  stale market prices as current quotes.
- Marketplace farmer asking prices remain user-generated listings and never
  enter verified market observations or their training data.
- Database ingestion remains insert/upsert through explicit dataset guards;
  inspect existing coverage before importing a new period, and do not overwrite
  valid records without an audited source correction workflow.

## Crop calendar and advisory acquisition attempt (2026-11-24)

- No new crop-calendar or advisory records were integrated. This is deliberate:
  publicly readable BBS/BAMIS documents did not provide a clear dataset-level
  redistribution licence, and the BAMIS site reserves rights. Public access is
  not treated as permission to bulk copy their calendar tables into the API.
- The BBS Yearbook of Agricultural Statistics 2022 (published May 2023) crop calendar (section 1.8,
  pp. 23–30) contains national sowing/transplanting, harvest, and seed-rate
  tables for many crops, but no Cumilla/Chattogram-specific rows. It is static
  historical guidance, not a current district advisory. No fertilizer-dose or
  pest-management records were extracted from it.
- BAMIS lists 33 crop-weather calendars and exposes region-specific calendar
  pages. Two English PDFs were machine-readable enough to inspect: Green Gram
  (Robi), Chattogram and Lentil, Cumilla. The lentil stage-week row has an
  internal column-count mismatch; it was not normalized. The Green Gram PDF is
  explicitly dated only by its URL asset path, not by a confirmed publication
  date. Neither was imported because BAMIS reuse terms remain unresolved.
- The Mendeley dataset has an explicit CC BY 4.0 listing and is the clearest
  reuse candidate. Its public dataset API returned HTTP 401 without OAuth2; no
  local or hosted access token is configured. It reports 104 crops, but
  geographic coverage and row-level provenance must be checked from the actual
  CSVs before any record is accepted. It is not yet counted as acquired.
- Required access: use the Mendeley dataset page's **Download All** action and
  provide the ZIP/CSV inside the workspace, or configure an authorized Mendeley
  API client locally (do not share client secrets). For official BAMIS data,
  request written redistribution/reuse terms and a confirmed publication date
  or current structured feed from DAE/BAMIS. BBS reuse terms are also needed
  before integrating its table.
- Validation run: `node --test tests/modis.latest.quality.test.js` passed 8/8;
  crop catalog/calendar JSON parsed; relevant controller/catalog service
  syntax checks passed; `git diff --check` passed. No crop-calendar API
  integration test ran because no new records were authorized for integration.

## Licensed research phenology acquisition (2026-11-24)

This later section supersedes the earlier statement above that the Mendeley
phenology candidate had not been acquired. NASA POWER, GPM IMERG, and AgriPriceBD
were not downloaded or reprocessed in this phase.

- **Dataset:** [AgriClimateBD, Version 2](https://data.mendeley.com/datasets/tb5x9gw2pt/2),
  DOI `10.17632/tb5x9gw2pt.2`, published 2026-06-23, CC BY 4.0. Attribution:
  Basunia, M. S.; Biswas, J.; Kumar, S. (2026), *AgriClimateBD: A Satellite
  Enriched Precision Agriculture Dataset for Bangladesh*, Version 2, Mendeley
  Data, DOI above. License and attribution are carried in processed JSON.
- **Acquisition:** public Download All archive, 337,769 bytes; SHA-256
  `02D7339C8F9878AD93EEFE2EB5FB511B6763097A96E4D5C8E0ED5B806ED505D5`.
  The archive contains a 4,607-row CSV and its data dictionary PDF. The page
  describes a survey of 223 farmers, 73 crop types, and all 64 districts; the
  CSV actually has 72 valid crop names plus one spreadsheet `#REF!` error.
- **Validation:** 4,606 rows accepted as research phenology records; 1 row
  rejected for the formula-error crop name. There are 72 crop names, 64
  districts, and three seasons; no duplicate `(district, crop, season)` keys.
  Cumilla and Chattogram each have 72 accepted rows. Source month labels are
  preserved as month-level periods, with no inferred day or year. 640 growth
  periods explicitly say “No need to do” and remain null; 128 harvest periods
  contain an unparsed “Throuout The year” value and remain null. These are
  quality flags, not filled values. The source does not supply row-level sample
  sizes or a survey collection year, so periods must not be presented as current
  schedules or official advice.
- **Excluded fields:** all NASA POWER-derived climate fields were excluded
  (including because max relative humidity is below min relative humidity in
  all 4,607 source rows, and climate data would duplicate prior acquisitions).
  BBS area/production statistics and the 416 nonnumeric `AP Ratio` values were
  also excluded. No fertilizer or pesticide recommendations were sourced.
- **Integration:** the 4,606 records are stored in the new static research data
  file `data/crops/agriclimatedbd_research_phenology.json` and exposed through
  `GET /api/v1/crop-calendar/research-phenology`. This follows the existing
  static JSON crop-calendar architecture; no Mongo collection or production
  database write was appropriate or performed. The API returns source/license,
  research type, quality notes, filters, and pagination, and explicitly marks
  the records as not official recommendations. The existing four-record
  official crop calendar is unchanged.
- **Verification:** Python parser tests passed 5/5; Node research API tests
  passed 5/5, including an HTTP request through the existing route and checks
  that the official calendar remains unchanged. Python compile, JavaScript
  syntax checks, and `git diff --check` passed. MongoDB integration was not
  needed for this static dataset; production DB access was not attempted.

The older Bangladesh Agricultural Datasets v1 candidate (`8pvfs5wyzf/1`) remains
pending separately: its metadata API previously required Mendeley OAuth, and
its v5 public archive has now been inspected instead. Version 5 (the current
inspected version) is the integrated version below; v1 itself was not
downloaded. BAMIS and BBS official calendars remain blocked on reuse terms; this
licensed research layer is not a substitute for those official recommendations.

## Additional licensed national phenology acquisition (2026-11-24)

- **Dataset:** [Bangladesh Agricultural Datasets, Version 5](https://data.mendeley.com/datasets/8pvfs5wyzf/5),
  DOI `10.17632/8pvfs5wyzf.5`, published 2021-12-29, CC BY 4.0. The publisher
  describes transplanting/growth/harvest periods compiled from BBS Yearbook of
  Agricultural Statistics 2020 and a crop-seasons article. Attribution:
  Rahman, M. B.; Chakma, J. D. (2021), *Bangladesh Agricultural Datasets*,
  Version 5, Mendeley Data, DOI above.
- **Acquisition:** public archive download, 24,661 bytes; SHA-256
  `DCD2E634B871F818575AF59A5823742A8E383FE9B502A01FC403F1DAF04FC132`.
  The raw CSV contains 103 rows and 11 columns. No registration was required.
- **Validation/deduplication:** all 103 rows have crop, season, and period text;
  seasons are Rabi, Kharif 1, and Kharif 2. Seventeen exact normalized
  crop/season/period identities duplicate AgriClimateBD v2 and were skipped.
  The other 86 records were accepted, with 86 crop labels across three seasons;
  none has district or upazila detail, so all are marked national-only and are
  excluded whenever the API request filters by district. Sixteen growth fields
  explicitly say “No need to do” and remain null; three misspelled harvest
  periods remain null and flagged. Source crop spellings and cultivar/product
  variants are retained verbatim.
- **Excluded fields:** all 103 rows have maximum relative humidity below
  minimum relative humidity, so temperature/humidity values were rejected.
  Normalized values and cluster labels are derived outputs and were excluded.
  No field values were corrected or treated as official recommendations.
- **Integration/API:** the 86 records are stored separately in
  `data/crops/bangladesh_agricultural_datasets_v5_phenology.json`, with the raw
  archive retained for reproducibility. The existing public research
  phenology endpoint now returns both licensed sources, carries source ID,
  version, source link, license, attribution, evidence type, and geography on
  each record, and provides both source manifests. District-filtered responses
  include only district-level AgriClimateBD rows; national data are never
  relabeled as Cumilla/Chattogram data. Official calendar records remain
  unchanged.
- **Verification:** the AgriClimateBD + v5 parser suite passed 8/8; research
  API tests passed 6/6, including an actual HTTP request through Express and a
  check that national records do not appear in district-filtered results.
  Python compile, JavaScript syntax checks, and whitespace validation passed.
  The architecture stores crop reference data as static JSON; no MongoDB write
  or production database access was needed or attempted.

