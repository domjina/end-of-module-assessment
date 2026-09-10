"""Baseline persistence tests.

These tests characterise the *current* behaviour of ``RecordCollection`` /
``RecordManager`` (imported from ``src.record.record_management``) so that later
persistence/validation changes have a regression guard. They do not change
application source.

Cases B01-B09. All data lives in ``tempfile`` directories; the real
``src/data/records.jsonl`` is never created or touched.

Run from the repository root with a Python >= 3.11 interpreter::

    python -m unittest discover -s tests -t . -v
    # or
    python -m unittest tests.test_nhi_persistence_baseline -v
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime

from src.record.record_management import RecordCollection, RecordManager
from src.record.record_types import RecordType

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL_DATA_FILE = os.path.join(REPO_ROOT, "src", "data", "records.jsonl")

CLIENT_DATA = {
    "record_type": "client",
    "name": "Alice Example",
    "address_line_1": "1 Test Street",
    "address_line_2": "",
    "address_line_3": "",
    "city": "London",
    "state": "",
    "zip_code": "SW1A 1AA",
    "country": "United Kingdom",
    "phone_number": "01234567890",
}
AIRLINE_DATA = {"record_type": "airline", "company_name": "Test Airways"}
FLIGHT_DATA = {
    "client_id": 1,
    "airline_id": 1,
    "date": datetime(2026, 9, 10, 14, 30),
    "start_city": "London",
    "end_city": "New York",
}


class PersistenceBaseline(unittest.TestCase):
    def setUp(self) -> None:
        self._real_data_existed = os.path.exists(REAL_DATA_FILE)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "records.jsonl")

    def tearDown(self) -> None:
        # The real data file must be untouched by any test in this module.
        self.assertEqual(
            os.path.exists(REAL_DATA_FILE),
            self._real_data_existed,
            "tests must not create or remove src/data/records.jsonl",
        )

    # ----- helpers -------------------------------------------------------
    def _new_collection(self) -> RecordCollection:
        return RecordCollection(self.path)

    def _read_bytes(self) -> bytes:
        with open(self.path, "rb") as fh:
            return fh.read()

    # ----- B01 ---------------------------------------------------------------
    def test_B01_missing_file_in_existing_dir_starts_empty(self) -> None:
        col = self._new_collection()
        self.assertEqual(col.records, [])
        self.assertIsInstance(col.records, list)
        # Observed (not a brief requirement): current implementation eagerly
        # creates the file via save() on FileNotFoundError.
        self.assertTrue(os.path.exists(self.path))
        self.assertEqual(os.path.getsize(self.path), 0)
        self.assertFalse(
            os.path.exists(REAL_DATA_FILE) and not self._real_data_existed
        )

    # ----- B02 ---------------------------------------------------------------
    def test_B02_empty_and_blank_line_files_load_as_empty_without_rewrite(self) -> None:
        for label, content in (("empty", ""), ("blank-lines", "\n   \n\t\n")):
            with self.subTest(file=label):
                with open(self.path, "w", encoding="utf-8") as fh:
                    fh.write(content)
                before = self._read_bytes()
                col = self._new_collection()
                self.assertEqual(col.records, [])
                self.assertEqual(
                    self._read_bytes(), before, "load() must not rewrite the file"
                )

    # ----- B03 ---------------------------------------------------------------
    def test_B03_loads_existing_mixed_jsonl_with_expected_types(self) -> None:
        rows = [
            {**CLIENT_DATA, "id": 1},
            {**AIRLINE_DATA, "id": 1},
            {
                "client_id": 1,
                "airline_id": 1,
                "date": "2026-09-10T14:30:00",
                "start_city": "London",
                "end_city": "New York",
            },
        ]
        with open(self.path, "w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")

        col = self._new_collection()
        self.assertEqual(len(col.records), 3)
        client = next(r for r in col.records if r.get("record_type") == "client")
        airline = next(r for r in col.records if r.get("record_type") == "airline")
        flight = next(r for r in col.records if "date" in r)
        self.assertEqual(client["name"], "Alice Example")
        self.assertIsInstance(client["id"], int)
        self.assertEqual(airline["company_name"], "Test Airways")
        # _convert_dates() turns the ISO string back into a datetime.
        self.assertIsInstance(flight["date"], datetime)
        self.assertEqual(flight["date"], datetime(2026, 9, 10, 14, 30))

    # ----- B04 ---------------------------------------------------------------
    def test_B04_save_then_reload_round_trips_unicode_newline_datetime(self) -> None:
        col = self._new_collection()
        mgr = RecordManager(col)
        weird = {**CLIENT_DATA, "name": "Ünîcodé Ñame\nSecond line"}
        mgr.create_record(RecordType.CLIENT, dict(weird))
        mgr.create_record(RecordType.AIRLINE, dict(AIRLINE_DATA))
        mgr.create_record(RecordType.FLIGHT, dict(FLIGHT_DATA))

        with open(self.path, "r", encoding="utf-8") as fh:
            lines = [ln for ln in fh.read().splitlines() if ln.strip()]
        self.assertEqual(len(lines), 3)
        for ln in lines:
            self.assertIsInstance(json.loads(ln), dict)

        reloaded = RecordCollection(self.path)
        self.assertEqual(len(reloaded.records), 3)
        client = next(r for r in reloaded.records if r.get("record_type") == "client")
        flight = next(r for r in reloaded.records if "date" in r)
        self.assertEqual(client["name"], "Ünîcodé Ñame\nSecond line")
        self.assertIsInstance(flight["date"], datetime)
        self.assertEqual(flight["date"], FLIGHT_DATA["date"])

    # ----- B05 ---------------------------------------------------------------
    def test_B05_valid_create_persists_and_is_reloadable(self) -> None:
        col = self._new_collection()
        mgr = RecordManager(col)
        mgr.create_record(RecordType.CLIENT, dict(CLIENT_DATA))

        self.assertEqual(len(col.records), 1)
        self.assertEqual(col.records[0]["id"], 1)

        fresh = RecordCollection(self.path)
        self.assertEqual(len(fresh.records), 1)
        self.assertEqual(fresh.records[0]["name"], "Alice Example")

    # ----- B06 ---------------------------------------------------------------
    def test_B06_valid_update_changes_only_target_and_reloads(self) -> None:
        col = self._new_collection()
        mgr = RecordManager(col)
        mgr.create_record(RecordType.CLIENT, dict(CLIENT_DATA))
        mgr.create_record(RecordType.CLIENT, {**CLIENT_DATA, "name": "Bob Second"})

        updated = {**CLIENT_DATA, "name": "Alice Updated"}
        ok = mgr.update_record(RecordType.CLIENT, dict(updated), record_id=1)
        self.assertTrue(ok)

        fresh = RecordCollection(self.path)
        by_id = {r["id"]: r for r in fresh.records}
        self.assertEqual(by_id[1]["name"], "Alice Updated")
        self.assertEqual(by_id[2]["name"], "Bob Second")

    # ----- B07 ---------------------------------------------------------------
    def test_B07_valid_delete_removes_from_memory_and_file(self) -> None:
        col = self._new_collection()
        mgr = RecordManager(col)
        mgr.create_record(RecordType.CLIENT, dict(CLIENT_DATA))
        mgr.create_record(RecordType.CLIENT, {**CLIENT_DATA, "name": "Bob Second"})

        ok = mgr.delete_record(RecordType.CLIENT, record_id=1)
        self.assertTrue(ok)
        self.assertEqual([r["id"] for r in col.records], [2])

        fresh = RecordCollection(self.path)
        self.assertEqual([r["id"] for r in fresh.records], [2])

    # ----- B08 ---------------------------------------------------------------
    def test_B08_update_or_delete_missing_record_returns_false_and_no_write(self) -> None:
        col = self._new_collection()
        mgr = RecordManager(col)
        mgr.create_record(RecordType.CLIENT, dict(CLIENT_DATA))
        before = self._read_bytes()

        self.assertFalse(mgr.delete_record(RecordType.CLIENT, record_id=999))
        self.assertFalse(
            mgr.update_record(RecordType.CLIENT, dict(CLIENT_DATA), record_id=999)
        )
        self.assertEqual(len(col.records), 1)
        self.assertEqual(self._read_bytes(), before, "no-op must not rewrite the file")

    # ----- B09 ---------------------------------------------------------------
    def test_B09_create_missing_required_field_rejected_before_save(self) -> None:
        col = self._new_collection()
        mgr = RecordManager(col)
        before = self._read_bytes()
        # Current structural guard is the frozen dataclass constructor.
        with self.assertRaises(TypeError):
            mgr.create_record(RecordType.CLIENT, {"record_type": "client", "name": "X"})
        self.assertEqual(col.records, [])
        self.assertEqual(self._read_bytes(), before, "rejected create must not write")

    # ----- supporting observation: per-type id allocation ------------------
    def test_get_next_id_is_sequential_within_each_type(self) -> None:
        col = self._new_collection()
        mgr = RecordManager(col)
        for _ in range(3):
            mgr.create_record(RecordType.CLIENT, dict(CLIENT_DATA))
        for _ in range(2):
            mgr.create_record(RecordType.AIRLINE, dict(AIRLINE_DATA))
        ids = [(r["record_type"], r["id"]) for r in col.records]
        self.assertEqual(
            ids,
            [("client", 1), ("client", 2), ("client", 3), ("airline", 1), ("airline", 2)],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
