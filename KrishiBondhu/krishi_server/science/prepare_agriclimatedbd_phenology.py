"""Validate and prepare the licensed AgriClimateBD survey phenology fields.

Climate and BBS production fields are deliberately excluded: the climate
features duplicate NASA POWER inputs and failed a humidity min/max invariant.
This output is research context, never an official recommendation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import zipfile
from collections import Counter
from datetime import date
from pathlib import Path


HERE = Path(__file__).resolve().parent
DEFAULT_ARCHIVE = HERE / "data/raw/agriclimatedbd_v2.zip"
DEFAULT_OUTPUT = HERE.parent / "data/crops/agriclimatedbd_research_phenology.json"
DATASET_ID = "10.17632/tb5x9gw2pt.2"
SOURCE_URL = "https://data.mendeley.com/datasets/tb5x9gw2pt/2"
LICENSE = "CC BY 4.0"
VALID_SEASONS = {"Rabi", "Kharif 1", "Kharif 2"}
MONTHS = {
    "jan", "january", "feb", "february", "mar", "march", "apr", "april",
    "may", "jun", "june", "jul", "july", "aug", "august", "sep",
    "sept", "september", "oct", "october", "nov", "november", "dec",
    "december",
}
MONTH_TOKEN = re.compile(r"[A-Za-z]+")


def validate_period(value: str) -> tuple[str | None, str | None]:
    """Preserve source period wording; accept only recognized month labels."""
    raw = (value or "").strip()
    if not raw:
        return None, "missing_in_source"
    if raw.casefold() == "no need to do":
        return None, "source_does_not_supply_period"
    tokens = MONTH_TOKEN.findall(raw)
    month_tokens = [token for token in tokens if token.casefold() in MONTHS]
    other_tokens = [
        token for token in tokens
        if token.casefold() not in MONTHS and token.casefold() not in {"to", "the"}
    ]
    if month_tokens and not other_tokens:
        return raw, None
    return None, "unparsed_source_period"


def _read_csv(archive_path: Path) -> list[dict[str, str]]:
    if not archive_path.is_file():
        raise FileNotFoundError(f"AgriClimateBD v2 archive not found: {archive_path}")
    with zipfile.ZipFile(archive_path) as archive:
        candidates = [
            name for name in archive.namelist()
            if Path(name).name.casefold() == "agriclimatebd.csv"
        ]
        if len(candidates) != 1:
            raise ValueError("Expected exactly one AgriclimateBD.csv in the source archive.")
        with archive.open(candidates[0]) as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
            reader = csv.DictReader(text)
            required = {"District", "Season", "Crop Name", "Transplant", "Growth", "Harvest"}
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise ValueError("AgriClimateBD CSV is missing required phenology columns.")
            return list(reader)


def prepare_records(rows: list[dict[str, str]]) -> tuple[list[dict], dict]:
    rejected = Counter()
    period_flags = Counter()
    records = []
    seen = set()
    districts = set()
    crops = set()
    seasons = set()

    for row_number, row in enumerate(rows, start=2):
        district = (row.get("District") or "").strip()
        crop = (row.get("Crop Name") or "").strip()
        season = (row.get("Season") or "").strip()
        if not district or not crop or not season:
            rejected["missing_identity_field"] += 1
            continue
        if crop.casefold() == "#ref!":
            rejected["spreadsheet_formula_error_crop_name"] += 1
            continue
        if season not in VALID_SEASONS:
            rejected["unsupported_season_value"] += 1
            continue

        key = (district.casefold(), crop.casefold(), season.casefold())
        if key in seen:
            rejected["duplicate_district_crop_season"] += 1
            continue
        seen.add(key)

        periods = {}
        flags = []
        for field, output_name in (
            ("Transplant", "transplant"),
            ("Growth", "growth"),
            ("Harvest", "harvest"),
        ):
            value, issue = validate_period(row.get(field, ""))
            periods[output_name] = value
            if issue:
                flag = f"{output_name}:{issue}"
                flags.append(flag)
                period_flags[flag] += 1

        # Source row number is tied to this fixed dataset version and supports
        # audit against the archived CSV without copying unrelated fields.
        source_key = f"{DATASET_ID}:{row_number}"
        record_id = hashlib.sha256(source_key.encode("utf-8")).hexdigest()[:20]
        records.append({
            "recordId": record_id,
            "sourceRowNumber": row_number,
            "cropName": crop,
            "district": district,
            "season": season,
            "periods": periods,
            "qualityFlags": flags,
            "evidenceType": "research_field_survey_period_summary",
            "isOfficialRecommendation": False,
        })
        districts.add(district)
        crops.add(crop)
        seasons.add(season)

    if not rows:
        raise ValueError("AgriClimateBD source CSV contains no records.")
    if len(districts) != 64:
        raise ValueError(f"Expected source coverage for 64 districts; found {len(districts)}.")
    if seasons != VALID_SEASONS:
        raise ValueError(f"Unexpected source season coverage: {sorted(seasons)}")
    if len({record["recordId"] for record in records}) != len(records):
        raise ValueError("Generated research record identifiers are not unique.")

    audit = {
        "downloadedRows": len(rows),
        "acceptedRows": len(records),
        "rejectedRows": sum(rejected.values()),
        "rejectedReasons": dict(sorted(rejected.items())),
        "periodQualityFlags": dict(sorted(period_flags.items())),
        "districtCount": len(districts),
        "cropNameCount": len(crops),
        "seasonCount": len(seasons),
        "targetDistrictRecordCounts": {
            district: sum(record["district"].casefold() == district.casefold() for record in records)
            for district in ("Cumilla", "Chattogram")
        },
    }
    return records, audit


def build_payload(rows: list[dict[str, str]], retrieved_at: str) -> dict:
    records, audit = prepare_records(rows)
    return {
        "metadata": {
            "title": "AgriClimateBD: A Satellite Enriched Precision Agriculture Dataset for Bangladesh",
            "datasetId": DATASET_ID,
            "datasetVersion": 2,
            "authors": ["Md Shohedozzaman Basunia", "Jahanur Biswas", "Sudip Kumar"],
            "sourceUrl": SOURCE_URL,
            "publishedDate": "2026-06-23",
            "retrievedDate": retrieved_at,
            "license": LICENSE,
            "attribution": "Basunia, M. S.; Biswas, J.; Kumar, S. (2026). AgriClimateBD: A Satellite Enriched Precision Agriculture Dataset for Bangladesh, Version 2. Mendeley Data. https://doi.org/10.17632/tb5x9gw2pt.2. Licensed CC BY 4.0.",
            "dataType": "research_dataset",
            "phenologyEvidence": "Survey-derived crop period summaries. Dataset description reports surveys involving 223 farmers; per-record sample count and survey/collection year are not provided.",
            "observationPeriod": None,
            "geographicLevel": "district as provided in source; no upazila-level records",
            "periodGranularity": "source month labels only; no day-level dates or calendar year",
            "recommendationStatus": "not_an_official_recommendation",
            "excludedFields": [
                "Area", "AP Ratio", "Avg Temp", "Max Temp", "Min Temp",
                "Avg Humidity", "Max Relative Humidity", "Min Relative Humidity",
                "Production", "Seasonal_Rainfall_total_mm",
                "Seasonal_Solar_Radiation_avg", "Seasonal_Wind_Speed_avg",
                "Seasonal_Evapotranspiration_avg", "pre_trans_month_*",
                "transplant_month_*", "post_trans_month_*",
            ],
            "exclusionReason": "Only survey-derived phenology periods are integrated. BBS statistics are outside this task; NASA POWER-derived climate summaries are excluded to prevent duplicate climate ingestion, and their max/min relative-humidity columns are inverted in every source row.",
            "qualityLimitations": [
                "Source contains spreadsheet formula error #REF! as a crop name; affected rows are rejected.",
                "Some Growth fields say 'No need to do' and one Harvest wording is misspelled; affected periods remain null and carry quality flags.",
                "Survey year and per-row sample counts are absent; periods are not current forecasts or official guidance.",
            ],
            "audit": audit,
            "records": records,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--retrieved-date", default=date.today().isoformat())
    args = parser.parse_args()

    rows = _read_csv(args.input)
    payload = build_payload(rows, args.retrieved_date)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    audit = payload["metadata"]["audit"]
    print(json.dumps({"output": str(args.output), **audit}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
