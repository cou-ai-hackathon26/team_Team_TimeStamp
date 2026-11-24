"""Prepare licensed, national-level research phenology from Mendeley v5.

Only source crop-period labels are retained. Climate/normalized features are
excluded, and exact crop-season-period duplicates already in AgriClimateBD v2
are skipped. This is historical secondary research data, not advice.
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
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARCHIVE = HERE / "data/raw/bangladesh_agricultural_datasets_v5.zip"
BASELINE = HERE.parent / "data/crops/agriclimatedbd_research_phenology.json"
OUTPUT = HERE.parent / "data/crops/bangladesh_agricultural_datasets_v5_phenology.json"
DATASET_ID = "10.17632/8pvfs5wyzf.5"
SOURCE_URL = "https://data.mendeley.com/datasets/8pvfs5wyzf/5"
LICENSE = "CC BY 4.0"
ATTRIBUTION = (
    "Rahman, M. B.; Chakma, J. D. (2021). Bangladesh Agricultural Datasets, "
    "Version 5. Mendeley Data. https://doi.org/10.17632/8pvfs5wyzf.5. CC BY 4.0."
)
SEASONS = {"Rabi", "Kharif 1", "Kharif 2"}
MONTHS = {
    "jan", "january", "feb", "february", "mar", "march", "apr", "april",
    "may", "jun", "june", "jul", "july", "aug", "august", "sep", "sept",
    "september", "oct", "october", "nov", "november", "dec", "december",
}


def _normalize(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().strip("'")).casefold()


def _period(value: str | None) -> tuple[str | None, str | None]:
    raw = (value or "").strip().strip("'")
    if not raw:
        return None, "missing_in_source"
    if raw.casefold() == "no need to do":
        return None, "source_marks_not_applicable"
    tokens = re.findall(r"[A-Za-z]+", raw)
    unknown = [token for token in tokens if token.casefold() not in MONTHS | {"to", "mid"}]
    if unknown or not any(token.casefold() in MONTHS for token in tokens):
        return None, "unparsed_source_period"
    return raw, None


def _load_csv(archive_path: Path) -> list[dict[str, str]]:
    with zipfile.ZipFile(archive_path) as archive:
        matches = [name for name in archive.namelist() if Path(name).name == "00. Bangladesh Agricultural Raw Data .csv"]
        if len(matches) != 1:
            raise ValueError("Expected exactly one raw Bangladesh agricultural CSV.")
        with archive.open(matches[0]) as handle:
            return list(csv.DictReader(io.TextIOWrapper(handle, encoding="utf-8-sig", newline="")))


def _baseline_identities(path: Path) -> set[tuple[str, str, str, str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    identities = set()
    for record in payload["metadata"]["records"]:
        periods = record["periods"]
        identities.add((
            _normalize(record["cropName"]), _normalize(record["season"]),
            _normalize(periods.get("transplant")), _normalize(periods.get("growth")),
            _normalize(periods.get("harvest")),
        ))
    return identities


def prepare_records(rows: list[dict[str, str]], baseline: set[tuple[str, str, str, str, str]]) -> tuple[list[dict], dict]:
    seen = set()
    accepted = []
    rejected = Counter()
    duplicates = 0
    flags = Counter()
    for row_number, row in enumerate(rows, start=2):
        crop = (row.get("Products name") or "").strip()
        season = (row.get("Season") or "").strip()
        if not crop or not season:
            rejected["missing_crop_or_season"] += 1
            continue
        if season not in SEASONS:
            rejected["unsupported_season"] += 1
            continue
        raw_periods = {name: row.get(source, "") for name, source in (
            ("transplant", "Transplant"), ("growth", "Growth"), ("harvest", "Harvest"),
        )}
        periods = {}
        quality_flags = []
        for name, value in raw_periods.items():
            periods[name], issue = _period(value)
            if issue:
                quality_flags.append(f"{name}:{issue}")
                flags[quality_flags[-1]] += 1
        identity = (_normalize(crop), _normalize(season), *(_normalize(periods[key]) for key in ("transplant", "growth", "harvest")))
        if identity in seen:
            rejected["duplicate_source_crop_season_period"] += 1
            continue
        seen.add(identity)
        if identity in baseline:
            duplicates += 1
            continue
        source_row = row_number
        digest = hashlib.sha256(f"{DATASET_ID}:{source_row}".encode()).hexdigest()[:20]
        accepted.append({
            "recordId": digest,
            "sourceRowNumber": source_row,
            "cropName": crop,
            "district": None,
            "geographicLevel": "national",
            "country": (row.get("Country") or "Bangladesh").strip(),
            "season": season,
            "periods": periods,
            "sourcePeriodLabels": {key: (value or "").strip().strip("'") for key, value in raw_periods.items()},
            "qualityFlags": quality_flags,
            "evidenceType": "secondary research phenology derived from BBS 2020 and a crop-seasons article",
            "dataType": "research_dataset",
            "isOfficialRecommendation": False,
            "sourceId": DATASET_ID,
            "sourceTitle": "Bangladesh Agricultural Datasets",
            "sourceVersion": 5,
            "sourceUrl": SOURCE_URL,
            "license": LICENSE,
            "attribution": ATTRIBUTION,
            "referenceYear": 2020,
            "observationPeriod": None,
        })
    audit = {
        "downloadedRows": len(rows),
        "acceptedRows": len(accepted),
        "exactDuplicatesSkippedAgainstAgriClimateBD": duplicates,
        "rejectedRows": sum(rejected.values()),
        "rejectedReasons": dict(rejected),
        "periodQualityFlags": dict(flags),
        "cropNameCount": len({item["cropName"] for item in accepted}),
        "seasonCount": len({item["season"] for item in accepted}),
        "geographicLevel": "national_only",
    }
    return accepted, audit


def prepare_dataset(archive_path: Path = ARCHIVE, baseline_path: Path = BASELINE, retrieved_date: str = "2026-11-24") -> dict:
    records, audit = prepare_records(_load_csv(archive_path), _baseline_identities(baseline_path))
    return {
        "metadata": {
            "title": "Bangladesh Agricultural Datasets",
            "datasetId": DATASET_ID,
            "datasetVersion": 5,
            "authors": ["Md. Bayazid Rahman", "Joy Dhon Chakma"],
            "sourceUrl": SOURCE_URL,
            "publishedDate": "2021-12-29",
            "retrievedDate": retrieved_date,
            "license": LICENSE,
            "attribution": ATTRIBUTION,
            "dataType": "research_dataset",
            "evidenceType": "secondary research phenology derived from BBS Yearbook 2020 and a crop-seasons article",
            "referenceYear": 2020,
            "observationPeriod": None,
            "geographicLevel": "national only; no district or upazila records",
            "periodGranularity": "source month labels only; no day-level dates",
            "recommendationStatus": "not_an_official_recommendation",
            "excludedFields": ["Crops Type", "Max Temp", "Min Temp", "Max Relative Humidity", "Min Relative Humidity", "Country normalization", "all normalized ML features", "cluster labels"],
            "exclusionReason": "Temperature and humidity columns are internally inconsistent (maximum RH is below minimum RH); normalized/cluster features are derived outputs, not raw agronomic observations.",
            "qualityLimitations": [
                "Source is a secondary compilation from BBS 2020 and a crop-seasons article; it is not a current calendar or official recommendation.",
                "Some crop labels are source spellings or cultivar/product variants and are retained verbatim.",
                "Month periods are not assigned an inferred year or exact dates; unparsed source periods remain null.",
                "Records with exact crop, season, and period duplicates of AgriClimateBD v2 are omitted to avoid duplicate phenology entries.",
            ],
            "audit": audit,
            "records": records,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--retrieved-date", default="2026-11-24")
    parser.add_argument("--archive", type=Path, default=ARCHIVE)
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    payload = prepare_dataset(args.archive, args.baseline, args.retrieved_date)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["metadata"]["audit"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
