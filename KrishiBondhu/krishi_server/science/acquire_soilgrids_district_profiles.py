"""Download and aggregate a small, licensed SoilGrids 2.0 topsoil subset.

The output is a district summary of modelled 250 m grid cells, not a field test.
Requires the existing Python Pillow installation to read GeoTIFF tiles.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from datetime import date
from pathlib import Path
from statistics import median
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_PATH = ROOT / "data/gis/bbs_admin2_cumilla_chattogram.geojson"
RAW_DIR = Path(__file__).resolve().parent / "data/raw/soilgrids_bangladesh"
OUTPUT_PATH = ROOT / "data/soil/soilgrids_district_profiles.json"
SERVICE_URL = "https://maps.isric.org/mapserv"
CRS_URL = "http://www.opengis.net/def/crs/EPSG/0/4326"
WCS_MAPS = {
    "phh2o": {"map": "/map/phh2o.map", "field": "phH2o", "unit": "pH", "divisor": 10},
    "soc": {"map": "/map/soc.map", "field": "soilOrganicCarbon", "unit": "g/kg", "divisor": 10},
    "clay": {"map": "/map/clay.map", "field": "clay", "unit": "%", "divisor": 10},
    "nitrogen": {"map": "/map/nitrogen.map", "field": "totalNitrogen", "unit": "g/kg", "divisor": 100},
}
DEPTH = "0-5cm"
QUANTILE = "Q0.5"
ATTRIBUTION = (
    "Poggio, L., de Sousa, L. M., Batjes, N. H., Heuvelink, G. B. M., Kempen, "
    "B., Ribeiro, E., and Rossiter, D. (2021). SoilGrids 2.0: producing soil "
    "information for the globe with quantified spatial uncertainty. SOIL, 7, "
    "217–240. https://doi.org/10.5194/soil-7-217-2021. CC BY 4.0."
)


def _district_features():
    data = json.loads(BOUNDARY_PATH.read_text(encoding="utf-8"))
    names = {"Comilla": ("cumilla", "Cumilla"), "Chittagong": ("chattogram", "Chattogram")}
    found = {}
    for feature in data["features"]:
        item = names.get(feature.get("properties", {}).get("adm2_en"))
        if item:
            code, name = item
            found[code] = {"code": code, "name": name, "feature": feature}
    if set(found) != {"cumilla", "chattogram"}:
        raise ValueError("Expected the existing BBS Cumilla and Chattogram ADM2 boundaries.")
    return found, data.get("provenance", {})


def _all_points(value):
    if isinstance(value, (list, tuple)) and value and isinstance(value[0], (int, float)):
        yield value
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _all_points(child)


def _bbox(features):
    points = [point for item in features.values() for point in _all_points(item["feature"]["geometry"]["coordinates"])]
    return (
        min(point[0] for point in points), min(point[1] for point in points),
        max(point[0] for point in points), max(point[1] for point in points),
    )


def _coverage_url(map_path, coverage_id, bbox):
    west, south, east, north = bbox
    params = [
        ("map", map_path), ("SERVICE", "WCS"), ("VERSION", "2.0.1"),
        ("REQUEST", "GetCoverage"), ("COVERAGEID", coverage_id),
        ("FORMAT", "GEOTIFF_INT16"), ("SUBSET", f"Long({west:.8f},{east:.8f})"),
        ("SUBSET", f"Lat({south:.8f},{north:.8f})"),
        ("SUBSETTINGCRS", CRS_URL), ("OUTPUTCRS", CRS_URL),
    ]
    return f"{SERVICE_URL}?{urlencode(params)}"


def _download_property(property_name, config, bbox, retrieval_date):
    coverage_id = f"{property_name}_{DEPTH}_{QUANTILE}"
    url = _coverage_url(config["map"], coverage_id, bbox)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"{retrieval_date}_{coverage_id}.tif"
    if path.exists():
        content = path.read_bytes()
        content_type = "cached local GeoTIFF"
        status = 200
    else:
        request = Request(url, headers={"User-Agent": "KrishiBondhu-soil-data-acquisition/1.0", "Accept": "image/tiff"})
        with urlopen(request, timeout=180) as response:
            content = response.read()
            content_type = response.headers.get("Content-Type", "")
            status = response.status
        if status != 200 or not content.startswith((b"II*\x00", b"MM\x00*")):
            raise RuntimeError(f"SoilGrids did not return GeoTIFF for {coverage_id} (HTTP {status}; {content_type}).")
        path.write_bytes(content)
    return path, hashlib.sha256(content).hexdigest(), url


def _rings_by_polygon(feature):
    geometry = feature["geometry"]
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"]]
    if geometry["type"] == "MultiPolygon":
        return geometry["coordinates"]
    raise ValueError(f"Unsupported boundary geometry type: {geometry['type']}")


def _row_intervals(rings, latitude, west, scale_x):
    intersections = []
    for ring in rings:
        for index, point_a in enumerate(ring):
            point_b = ring[index - 1]
            x1, y1 = point_a[:2]
            x2, y2 = point_b[:2]
            if (y1 > latitude) != (y2 > latitude):
                intersections.append(x1 + (latitude - y1) * (x2 - x1) / (y2 - y1))
    intersections.sort()
    intervals = []
    for left, right in zip(intersections[0::2], intersections[1::2]):
        start = math.ceil((left - west) / scale_x - 0.5)
        stop = math.ceil((right - west) / scale_x - 0.5)
        if stop > start:
            intervals.append((start, stop))
    return intervals


def build_polygon_mask(path: Path, feature):
    image = Image.open(path)
    tags = image.tag_v2
    if image.format != "TIFF" or image.mode not in {"I", "I;16", "I;16L", "I;16B"}:
        raise ValueError("SoilGrids WCS output is not an expected integer GeoTIFF.")
    tiepoints = tags.get(33922)
    scales = tags.get(33550)
    keys = tags.get(34735, ())
    if not tiepoints or not scales or 4326 not in keys:
        raise ValueError("GeoTIFF georeferencing is missing or not EPSG:4326.")
    raster_i, raster_j, _z, tie_lon, tie_lat, _tie_z = tiepoints[:6]
    scale_x, scale_y = scales[:2]
    width, height = image.size
    nodata = tags.get(42113)
    if isinstance(nodata, bytes):
        nodata = int(nodata.decode("ascii").strip("\x00 "))
    elif isinstance(nodata, str):
        nodata = int(nodata.strip("\x00 "))
    else:
        nodata = int(nodata) if nodata is not None else -32768
    row_intervals = [[] for _ in range(height)]
    for polygon in _rings_by_polygon(feature):
        rings = polygon
        for row in range(height):
            latitude = tie_lat - (row - raster_j + 0.5) * scale_y
            row_intervals[row].extend(_row_intervals(rings, latitude, tie_lon - raster_i * scale_x, scale_x))
    # Merge overlapping intervals so MultiPolygon intersections never count a
    # grid cell twice.
    for row, intervals in enumerate(row_intervals):
        merged = []
        for start, stop in sorted((max(0, a), min(width, b)) for a, b in intervals if b > 0 and a < width):
            if not merged or start > merged[-1][1]:
                merged.append([start, stop])
            else:
                merged[-1][1] = max(merged[-1][1], stop)
        row_intervals[row] = [(start, stop) for start, stop in merged if stop > start]
    return {
        "width": width,
        "height": height,
        "rowIntervals": row_intervals,
        "candidateGridCells": sum(stop - start for intervals in row_intervals for start, stop in intervals),
        "transform": (raster_i, raster_j, tie_lon, tie_lat, scale_x, scale_y),
        "nodata": nodata,
    }


def aggregate_geotiff(path: Path, mask, divisor):
    image = Image.open(path)
    tags = image.tag_v2
    tiepoints = tags.get(33922)
    scales = tags.get(33550)
    current_transform = (tiepoints[0], tiepoints[1], tiepoints[3], tiepoints[4], scales[0], scales[1])
    if image.size != (mask["width"], mask["height"]) or current_transform != mask["transform"]:
        raise ValueError("SoilGrids property layers have mismatched raster grids.")
    pixels = list(image.get_flattened_data())
    values = []
    for row, intervals in enumerate(mask["rowIntervals"]):
        offset = row * mask["width"]
        for start, stop in intervals:
            values.extend(value for value in pixels[offset + start:offset + stop] if value != mask["nodata"] and value >= 0)
    if not values:
        raise ValueError("No valid SoilGrids cells fall inside the district boundary.")
    raw_median = median(values)
    return {
        "value": round(raw_median / divisor, 3),
        "validGridCells": len(values),
        "candidateGridCells": mask["candidateGridCells"],
        "missingOrInvalidCells": mask["candidateGridCells"] - len(values),
        "gridCellResolutionMeters": 250,
        "depthCm": "0-5",
        "sourceQuantile": "0.50 (per-cell model median)",
    }


def acquire(retrieved_date=None, sleep_seconds=0.25):
    retrieval_date = retrieved_date or date.today().isoformat()
    districts, boundary_provenance = _district_features()
    bbox = _bbox(districts)
    raw_manifest = {}
    for property_name, config in WCS_MAPS.items():
        path, digest, url = _download_property(property_name, config, bbox, retrieval_date)
        raw_manifest[property_name] = {
            "file": path.relative_to(ROOT).as_posix(),
            "sha256": digest,
            "bytes": path.stat().st_size,
            "wcsUrl": url,
        }
        if sleep_seconds:
            time.sleep(sleep_seconds)

    profiles = {}
    for district_code, district in districts.items():
        attributes = {}
        first_path = RAW_DIR / f"{retrieval_date}_phh2o_{DEPTH}_{QUANTILE}.tif"
        mask = build_polygon_mask(first_path, district["feature"])
        for property_name, config in WCS_MAPS.items():
            coverage = aggregate_geotiff(RAW_DIR / f"{retrieval_date}_{property_name}_{DEPTH}_{QUANTILE}.tif", mask, config["divisor"])
            attributes[config["field"]] = {
                **coverage,
                "unit": config["unit"],
                "propertyCode": property_name,
                "qualityStatus": "modeled_estimate",
                "dataType": "spatial_model_prediction",
            }
        profiles[district_code] = {
            "districtCode": district_code,
            "district": district["name"],
            "geographicLevel": "district_polygon_summary",
            "aggregation": "Median of valid 250 m SoilGrids grid-cell Q0.5 predictions whose cell centers fall inside the existing BBS 2020 district boundary.",
            "attributes": attributes,
            "qualityFlags": [
                "modeled_not_field_measured",
                "district_summary_not_farm_specific",
                "global_model_not_locally_calibrated_in_this_response",
                "not_a_fertilizer_recommendation",
            ],
        }

    return {
        "metadata": {
            "dataset": "SoilGrids 2.0",
            "provider": "ISRIC - World Soil Information",
            "sourceUrl": "https://soilgrids.org/",
            "wcsDocumentationUrl": "https://docs.isric.org/globaldata/soilgrids/wcs.html",
            "sourceService": SERVICE_URL,
            "license": "CC BY 4.0",
            "attribution": ATTRIBUTION,
            "modelVersion": "SoilGrids 2.0",
            "retrievedDate": retrieval_date,
            "temporalType": "static spatial prediction; no observation date",
            "spatialResolutionMeters": 250,
            "depthIntervalCm": "0-5",
            "statistic": "Q0.5 (median) cell predictions, then median across valid cells inside district polygon",
            "properties": {
                "phh2o": {"field": "soil pH in water", "sourceUnit": "pH x 10", "outputUnit": "pH", "conversion": "divide source values by 10"},
                "soc": {"field": "soil organic carbon concentration", "sourceUnit": "dg/kg", "outputUnit": "g/kg", "conversion": "divide source values by 10"},
                "clay": {"field": "clay fraction", "sourceUnit": "g/kg", "outputUnit": "%", "conversion": "divide source values by 10"},
                "nitrogen": {"field": "total nitrogen", "sourceUnit": "cg/kg", "outputUnit": "g/kg", "conversion": "divide source values by 100"},
            },
            "unavailableProperties": ["available phosphorus", "available potassium"],
            "limitations": [
                "SoilGrids is a global prediction model; values are not direct measurements or local soil laboratory results.",
                "ISRIC advises against using SoilGrids at individual farm scale; district medians are broad regional summaries.",
                "No local calibration or district-level uncertainty interval was included in this extraction.",
                "The 0-5 cm layer is topsoil and does not represent deeper root-zone properties.",
                "Total nitrogen is a modeled soil property, not plant-available nitrogen and not a fertilizer dose.",
            ],
            "boundarySource": boundary_provenance,
            "rawFiles": raw_manifest,
        },
        "districts": profiles,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retrieved-date", help="Override retrieval date (YYYY-MM-DD) for reproducible rebuilds.")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    arguments = parser.parse_args()
    output = acquire(arguments.retrieved_date)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        district: {field: item["validGridCells"] for field, item in profile["attributes"].items()}
        for district, profile in output["districts"].items()
    }, sort_keys=True))
