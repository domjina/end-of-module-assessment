from datetime import datetime

from src.record.record_management import RecordCollection, RecordManager
from src.record.record_types import RecordType

def main():
    collection = RecordCollection("src/data/records.jsonl")
    record_manager = RecordManager(collection)

    client_data = {
        "record_type": "VIP",
        "name": "John Smith",
        "address_line_1": "123",
        "address_line_2": "",
        "address_line_3": "",
        "city": "London",
        "state": "",
        "zip_code": "SW1A 1AA",
        "country": "United Kingdom",
        "phone_number": "01234567890",
    }

    record_manager.create_record(RecordType.CLIENT, client_data)
    print("Client created and records saved")
    print(collection.records)

    airline_data = {
        "record_type": "boeing",
        "company_name": "boeing"
    }

    record_manager.create_record(RecordType.AIRLINE, airline_data)
    print("Airline created and records saved")
    print(collection.records)

    flight_data = {
        "client_id": 1,
        "airline_id": 1,
        "date": datetime(2026, 9, 10, 14, 30),
        "start_city": "London",
        "end_city": "New York"
    }

    record_manager.create_record(RecordType.FLIGHT, flight_data)
    print("Flight created and records saved")
    print(collection.records)

if __name__ == "__main__":
    main()
