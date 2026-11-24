import unittest
from pathlib import Path

from science.prepare_bangladesh_agricultural_datasets_v5 import (
    ARCHIVE,
    BASELINE,
    DATASET_ID,
    _load_csv,
    _period,
    _baseline_identities,
    prepare_dataset,
    prepare_records,
)


class BangladeshAgriculturalDatasetsV5Test(unittest.TestCase):
    def test_source_month_periods_are_preserved_and_unparsed_values_stay_missing(self):
        self.assertEqual(_period("Jan to March"), ("Jan to March", None))
        self.assertEqual(_period("No need to do"), (None, "source_marks_not_applicable"))
        self.assertEqual(_period("Throuout The year"), (None, "unparsed_source_period"))

    def test_real_archive_is_validated_and_exact_duplicates_are_skipped(self):
        payload = prepare_dataset(ARCHIVE, BASELINE)
        metadata = payload["metadata"]
        audit = metadata["audit"]
        self.assertEqual(metadata["datasetId"], DATASET_ID)
        self.assertEqual(metadata["license"], "CC BY 4.0")
        self.assertEqual(audit["downloadedRows"], 103)
        self.assertEqual(audit["exactDuplicatesSkippedAgainstAgriClimateBD"], 17)
        self.assertEqual(audit["acceptedRows"], 86)
        self.assertEqual(audit["rejectedRows"], 0)
        self.assertEqual(audit["geographicLevel"], "national_only")
        self.assertTrue(all(item["district"] is None for item in metadata["records"]))
        self.assertTrue(all(item["isOfficialRecommendation"] is False for item in metadata["records"]))
        self.assertTrue(all(item["sourceId"] == DATASET_ID for item in metadata["records"]))
        self.assertFalse(any("Max Temp" in item or "Cluster" in item for item in metadata["records"]))

    def test_no_duplicate_crop_season_period_records_survive(self):
        records, audit = prepare_records(_load_csv(ARCHIVE), _baseline_identities(BASELINE))
        identities = {
            (item["cropName"].casefold(), item["season"].casefold(), tuple(
                (item["periods"].get(key) or "").casefold()
                for key in ("transplant", "growth", "harvest")
            ))
            for item in records
        }
        self.assertEqual(len(identities), len(records))
        self.assertEqual(audit["acceptedRows"], len(records))


if __name__ == "__main__":
    unittest.main()
