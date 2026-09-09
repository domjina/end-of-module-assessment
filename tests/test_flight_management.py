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
        file_path = Path(self.temp_directory.name) / "records.jsonl"

        self.collection = RecordCollection(str(file_path))
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

    def tearDown(self):
        self.temp_directory.cleanup()

    def test_collection_starts_empty(self):
        self.assertEqual(self.collection.records, [])
