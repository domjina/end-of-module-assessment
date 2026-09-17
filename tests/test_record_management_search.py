"""Focused regression tests for multi-field Management search behaviour."""

import tempfile
import unittest
from pathlib import Path

from src.record.record_management import RecordCollection, RecordManager
from src.record.record_types import RecordType


CLIENT_DATA = {
    "name": "Alice",
    "address_line_1": "1 Hope Street",
    "address_line_2": "",
    "address_line_3": "",
    "city": "Liverpool",
    "state": "Merseyside",
    "zip_code": "L1 1AA",
    "country": "United Kingdom",
    "phone_number": "01515550123",
}


class MultiFieldSearchRegression(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        file_path = Path(self.temp_directory.name) / "records.jsonl"
        self.collection = RecordCollection(str(file_path))
        self.manager = RecordManager(self.collection)
        self.manager.create_record(RecordType.CLIENT, dict(CLIENT_DATA))

    def test_client_multi_field_search_rejects_partial_match(self):
        """A matching name must not hide a mismatching active city criterion."""
        results = self.manager.search_display_record(
            RecordType.CLIENT,
            name="Alice",
            city="Manchester",
        )

        self.assertEqual(results, [])

    def test_client_multi_field_search_returns_full_match(self):
        """A record is returned when every active Client criterion matches."""
        results = self.manager.search_display_record(
            RecordType.CLIENT,
            name="Alice",
            city="Liverpool",
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Alice")
        self.assertEqual(results[0]["city"], "Liverpool")


if __name__ == "__main__":
    unittest.main()
