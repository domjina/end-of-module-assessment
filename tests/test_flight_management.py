import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from src.record.record_management import (
    RecordCollection,
    RecordManager,
)
from src.record.record_types import RecordType


class TestFlightManagement(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.file_path = Path(self.temp_directory.name) / "records.jsonl"

        self.collection = RecordCollection(str(self.file_path))
        self.manager = RecordManager(self.collection)

    def create_client(self):
        self.manager.create_record(
            RecordType.CLIENT,
            {
                "record_type": "client",
                "name": "Maria Chen",
                "address_line_1": "1 Hope Street",
                "address_line_2": "",
                "address_line_3": "",
                "city": "Liverpool",
                "state": "Merseyside",
                "zip_code": "L1 1AA",
                "country": "United Kingdom",
                "phone_number": "0151 555 0101",
            },
        )

    def create_airline(self):
        self.manager.create_record(
            RecordType.AIRLINE,
            {
                "record_type": "airline",
                "company_name": "British Airways",
            },
        )

    def create_flight(self):
        flight_data = {
            "client_id": 1,
            "airline_id": 1,
            "date": datetime(2026, 9, 7, 10, 30),
            "start_city": "Liverpool",
            "end_city": "New York",
        }
        self.manager.create_record(RecordType.FLIGHT, flight_data)
        return flight_data

    def test_create_flight_when_client_and_airline_exist(self):
        self.create_client()
        self.create_airline()
        flight_date = datetime(2026, 9, 7, 10, 30)
        flight_data = {
            "client_id": 1,
            "airline_id": 1,
            "date": flight_date,
            "start_city": "Liverpool",
            "end_city": "New York",
        }
        self.manager.create_record(
            record_type=RecordType.FLIGHT,
            data=flight_data,
        )
        flight = self.collection.find(
            client_id=1,
            airline_id=1,
            date=flight_date,
        )
        self.assertIsNotNone(flight)
        self.assertEqual(flight["client_id"], 1)
        self.assertEqual(flight["airline_id"], 1)
        self.assertEqual(flight["start_city"], "Liverpool")
        self.assertEqual(flight["end_city"], "New York")

    def test_create_flight_rejects_missing_client(self):
        self.create_airline()
        flight_data = {
            "client_id": 1,
            "airline_id": 1,
            "date": datetime(2026, 9, 7, 10, 30),
            "start_city": "Liverpool",
            "end_city": "New York",
        }
        with self.assertRaisesRegex(
            ValueError,
            "Client ID 1 does not exist",
        ):
            self.manager.create_record(
                record_type=RecordType.FLIGHT,
                data=flight_data,
            )

        flights = [
            record
            for record in self.collection.records
            if "client_id" in record
        ]
        self.assertEqual(flights, [])

    def test_create_flight_rejects_missing_airline(self):
        self.create_client()
        flight_data = {
            "client_id": 1,
            "airline_id": 1,
            "date": datetime(2026, 9, 7, 10, 30),
            "start_city": "Liverpool",
            "end_city": "New York",
        }
        with self.assertRaisesRegex(
            ValueError,
            "Airline ID 1 does not exist",
        ):
            self.manager.create_record(
                record_type=RecordType.FLIGHT,
                data=flight_data,
            )

        flights = [
            record
            for record in self.collection.records
            if "airline_id" in record
        ]
        self.assertEqual(flights, [])

    def test_update_flight_rejects_missing_references_without_changes(self):
        """Rejected proposed references must not mutate memory or JSONL."""
        self.create_client()
        self.create_airline()
        original = self.create_flight()

        for field, missing_id, message in (
            ("client_id", 999, "Client ID 999 does not exist"),
            ("airline_id", 999, "Airline ID 999 does not exist"),
        ):
            with self.subTest(field=field):
                before_records = [dict(record) for record in self.collection.records]
                before_jsonl = self.file_path.read_bytes()
                proposed = {**original, field: missing_id}

                with self.assertRaisesRegex(ValueError, message):
                    self.manager.update_record(
                        RecordType.FLIGHT,
                        proposed,
                        **original,
                    )

                self.assertEqual(self.collection.records, before_records)
                self.assertEqual(self.file_path.read_bytes(), before_jsonl)
                reloaded = RecordCollection(str(self.file_path))
                self.assertEqual(reloaded.find(**original), original)

    def test_valid_flight_update_persists(self):
        """A valid proposed Flight update must still save and reload."""
        self.create_client()
        self.create_airline()
        original = self.create_flight()
        proposed = {**original, "end_city": "Paris"}

        updated = self.manager.update_record(
            RecordType.FLIGHT,
            proposed,
            **original,
        )

        self.assertTrue(updated)
        flights = [record for record in self.collection.records if "client_id" in record]
        self.assertEqual(flights, [proposed])
        reloaded = RecordCollection(str(self.file_path))
        self.assertEqual(reloaded.find(**proposed), proposed)
        self.assertIsInstance(reloaded.find(**proposed)["date"], datetime)

    def test_incomplete_flight_delete_preserves_all_records(self):
        """Every part of the five-field Flight identity is required to delete."""
        self.create_client()
        self.create_airline()
        identity = self.create_flight()
        before_records = [dict(record) for record in self.collection.records]
        before_jsonl = self.file_path.read_bytes()

        for missing_field in identity:
            with self.subTest(missing_field=missing_field):
                incomplete = {
                    key: value
                    for key, value in identity.items()
                    if key != missing_field
                }

                deleted = self.manager.delete_record(
                    RecordType.FLIGHT,
                    **incomplete,
                )

                self.assertFalse(deleted)
                self.assertEqual(self.collection.records, before_records)
                self.assertEqual(self.file_path.read_bytes(), before_jsonl)
                self.assertIsNotNone(
                    self.collection.find(record_type="client", id=1)
                )
                self.assertIsNotNone(
                    self.collection.find(record_type="airline", id=1)
                )
                self.assertEqual(self.collection.find(**identity), identity)

    def test_flight_multi_field_search_uses_all_active_criteria(self):
        """Flight search must use AND semantics for all supplied fields."""
        self.create_client()
        self.create_airline()
        flight = self.create_flight()

        no_match = self.manager.search_display_record(
            RecordType.FLIGHT,
            start_city="Liverpool",
            end_city="Manchester",
        )
        match = self.manager.search_display_record(
            RecordType.FLIGHT,
            start_city="Liverpool",
            end_city="New York",
        )

        self.assertEqual(no_match, [])
        self.assertEqual(match, [flight])

    def tearDown(self):
        self.temp_directory.cleanup()

    def test_collection_starts_empty(self):
        self.assertEqual(self.collection.records, [])
