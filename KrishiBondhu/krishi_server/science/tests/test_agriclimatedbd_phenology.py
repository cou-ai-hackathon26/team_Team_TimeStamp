import unittest

from science.prepare_agriclimatedbd_phenology import (
    DEFAULT_ARCHIVE,
    _read_csv,
    build_payload,
)


class AgriClimateBDPhenologyAcquisitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = build_payload(_read_csv(DEFAULT_ARCHIVE), "2026-11-24")
        cls.metadata = cls.payload["metadata"]
        cls.records = cls.metadata["records"]

    def test_pinned_source_license_and_attribution_are_preserved(self):
        self.assertEqual(self.metadata["datasetId"], "10.17632/tb5x9gw2pt.2")
        self.assertEqual(self.metadata["license"], "CC BY 4.0")
        self.assertIn("doi.org/10.17632/tb5x9gw2pt.2", self.metadata["attribution"])
        self.assertEqual(self.metadata["dataType"], "research_dataset")
        self.assertFalse(self.records[0]["isOfficialRecommendation"])

    def test_rows_are_deduplicated_and_invalid_crop_formula_is_rejected(self):
        audit = self.metadata["audit"]
        self.assertEqual(audit["downloadedRows"], 4607)
        self.assertEqual(audit["acceptedRows"], 4606)
        self.assertEqual(audit["rejectedRows"], 1)
        self.assertEqual(audit["rejectedReasons"], {"spreadsheet_formula_error_crop_name": 1})
        self.assertEqual(len({r["recordId"] for r in self.records}), len(self.records))
        self.assertEqual(
            len({(r["district"].casefold(), r["cropName"].casefold(), r["season"].casefold()) for r in self.records}),
            len(self.records),
        )
        self.assertTrue(all(r["cropName"] != "#REF!" for r in self.records))

    def test_district_and_season_coverage_is_preserved_as_source_scope(self):
        audit = self.metadata["audit"]
        self.assertEqual(audit["districtCount"], 64)
        self.assertEqual(audit["cropNameCount"], 72)
        self.assertEqual(audit["seasonCount"], 3)
        self.assertEqual(audit["targetDistrictRecordCounts"], {"Cumilla": 72, "Chattogram": 72})
        self.assertEqual(self.metadata["observationPeriod"], None)
        self.assertIn("no upazila-level", self.metadata["geographicLevel"])

    def test_unavailable_or_malformed_periods_remain_null_and_flagged(self):
        audit_flags = self.metadata["audit"]["periodQualityFlags"]
        self.assertEqual(audit_flags["growth:source_does_not_supply_period"], 640)
        self.assertEqual(audit_flags["harvest:unparsed_source_period"], 128)
        growth_missing = [r for r in self.records if "growth:source_does_not_supply_period" in r["qualityFlags"]]
        harvest_unparsed = [r for r in self.records if "harvest:unparsed_source_period" in r["qualityFlags"]]
        self.assertTrue(growth_missing)
        self.assertTrue(harvest_unparsed)
        self.assertTrue(all(r["periods"]["growth"] is None for r in growth_missing))
        self.assertTrue(all(r["periods"]["harvest"] is None for r in harvest_unparsed))

    def test_climate_and_bbs_statistics_are_not_integrated(self):
        excluded = self.metadata["excludedFields"]
        self.assertIn("Production", excluded)
        self.assertIn("Seasonal_Rainfall_total_mm", excluded)
        self.assertTrue(all("Rainfall" not in r and "Production" not in r for r in self.records))
        self.assertIn("humidity", self.metadata["exclusionReason"])


if __name__ == "__main__":
    unittest.main()
