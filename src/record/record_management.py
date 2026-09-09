from abc import ABC, abstractmethod
import dataclasses
import json
from datetime import datetime
from src.record.client_record import ClientRecord
from src.record.airline_record import AirlineRecord
from src.record.flight_record import FlightRecord
from src.record.record_types import RecordType

class RecordCollection:
    def __init__(self, file_path: str = "src/data/records.jsonl"):
        self.records: list[dict] = []
        self.file_path = file_path
        self.load()

    def get_next_id(self, record_type: str) -> int:
        max_id = 0
        for record in self.records:
            if record_type == RecordType.CLIENT.value:
                if "id" in record and record.get("record_type") == record_type:
                    max_id = max(max_id, record["id"])
                if "client_id" in record:
                    max_id = max(max_id, record["client_id"])

            elif record_type == RecordType.AIRLINE.value:
                if "id" in record and record.get("record_type") == record_type:
                    max_id = max(max_id, record["id"])
                if "airline_id" in record:
                    max_id = max(max_id, record["airline_id"])

        return max_id + 1

    def add(self, record: dict) -> None:
        self.records.append(record)
        self.save()

    def delete(self, record_type: str | None = None, **criteria) -> bool:
        for index, record in enumerate(self.records):
            if record_type is not None and record.get("record_type") != record_type:
                continue

            if all(record.get(key) == value for key, value in criteria.items()):
                del self.records[index]
                self.save()
                return True
        return False

    def update(self, new_record: dict, **criteria) -> bool:
        for index, record in enumerate(self.records):
            if all(record.get(key) == value for key, value in criteria.items()):
                self.records[index] = new_record
                self.save()
                return True

        return False

    def find(self, record_type: str | None = None, **criteria) -> dict | None:
        for record in self.records:
            if record_type is not None and record.get("record_type") != record_type:
                continue

            if all(record.get(key) == value for key, value in criteria.items()):
                return record

        return None

    def save(self) -> None:
        with open(self.file_path, "w", encoding="utf-8") as file:
            for record in self.records:
                json.dump(
                    record,
                    file,
                    default=self._json_serializer
                )
                file.write("\n")

    def load(self) -> None:
        try:
            with open(self.file_path, "r", encoding="utf-8") as file:
                self.records = [
                    json.loads(line)
                    for line in file
                    if line.strip()
                ]
            self._convert_dates()
        except FileNotFoundError:
            self.records = []
            self.save()

    @staticmethod
    def _json_serializer(value):
        if isinstance(value, datetime):
            return value.isoformat()
        raise TypeError(
            f"Object of type {type(value).__name__} is not JSON serializable"
        )

    def _convert_dates(self) -> None:
        for record in self.records:
            if "date" in record and isinstance(record["date"], str):
                record["date"] = datetime.fromisoformat(record["date"])

class RecordManagement(ABC):
    @abstractmethod
    def create_record(self, data: dict) -> None:
        ...

    @abstractmethod
    def delete_record(self, **criteria) -> bool:
        ...

    @abstractmethod
    def update_record(self, data: dict, **criteria) -> bool:
        ...

    @abstractmethod
    def search_display_record(self, **criteria) -> dict | None:
        ...

class ClientManagement(RecordManagement):
    def __init__(self, collection: RecordCollection):
        self.collection = collection

    def create_record(self, data: dict) -> None:
        data.pop("record_type", None)
        next_id = self.collection.get_next_id(RecordType.CLIENT.value)
        client = ClientRecord(id=next_id, record_type=RecordType.CLIENT.value, **data)
        self.collection.add(dataclasses.asdict(client))

    def delete_record(self, **criteria) -> bool:
        return self.collection.delete(
            record_type=RecordType.CLIENT.value,
            id=criteria["record_id"]
        )

    def update_record(self, data: dict, **criteria) -> bool:
        data.pop("record_type", None)
        record_id = criteria["record_id"]

        client = ClientRecord(
            id=record_id,
            record_type=RecordType.CLIENT.value,
            **data
        )

        return self.collection.update(
            dataclasses.asdict(client),
            id=record_id,
            record_type=RecordType.CLIENT.value
        )

    def search_display_record(self, **criteria) -> dict | None:
        return self.collection.find(
            record_type=RecordType.CLIENT.value,
            id=criteria["record_id"]
        )

class AirlineManagement(RecordManagement):
    def __init__(self, collection: RecordCollection):
        self.collection = collection

    def create_record(self, data: dict) -> None:
        data.pop("record_type", None)
        next_id = self.collection.get_next_id(RecordType.AIRLINE.value)
        airline = AirlineRecord(id=next_id, record_type=RecordType.AIRLINE.value, **data)
        self.collection.add(dataclasses.asdict(airline))

    def delete_record(self, **criteria) -> bool:
        return self.collection.delete(
            record_type=RecordType.AIRLINE.value,
            id=criteria["record_id"]
        )

    def update_record(self, data: dict, **criteria) -> bool:
        data.pop("record_type", None)
        record_id = criteria["record_id"]
        airline = AirlineRecord(
            id=record_id,
            record_type=RecordType.AIRLINE.value,
            **data
        )
        return self.collection.update(
            dataclasses.asdict(airline),
            id=record_id,
            record_type=RecordType.AIRLINE.value
        )

    def search_display_record(self, **criteria) -> dict | None:
        return self.collection.find(
            record_type=RecordType.AIRLINE.value,
            id=criteria["record_id"]
        )

class FlightManagement(RecordManagement):
    def __init__(self, collection: RecordCollection):
        self.collection = collection

    def create_record(self, data: dict) -> None:
        client_id = data["client_id"]
        airline_id = data["airline_id"]
        client = self.collection.find(
            record_type=RecordType.CLIENT.value,
            id=client_id
        )
        airline = self.collection.find(
            record_type=RecordType.AIRLINE.value,
            id=airline_id
        )
        if client is None:
            raise ValueError(f"Client ID {client_id} does not exist")
        if airline is None:
            raise ValueError(f"Airline ID {airline_id} does not exist")
        flight = FlightRecord(**data)
        self.collection.add(dataclasses.asdict(flight))

    def delete_record(self, **criteria) -> bool:
        return self.collection.delete(
            client_id=criteria["client_id"],
            airline_id=criteria["airline_id"],
            date=criteria["date"]
        )

    def update_record(self, data: dict, **criteria) -> bool:
        client_id = criteria["client_id"]
        airline_id = criteria["airline_id"]

        flight = FlightRecord(
            client_id=client_id,
            airline_id=airline_id,
            **data
        )
        return self.collection.update(
            dataclasses.asdict(flight),
            client_id=client_id,
            airline_id=airline_id,
            date=criteria["date"]
        )

    def search_display_record(self, **criteria) -> dict | None:
        client_id = criteria["client_id"]
        airline_id = criteria["airline_id"]
        return self.collection.find(
            client_id=client_id,
            airline_id=airline_id,
            date=criteria["date"]
        )

class RecordManager:
    def __init__(self, collection: RecordCollection):
        self.client_management = ClientManagement(collection)
        self.airline_management = AirlineManagement(collection)
        self.flight_management = FlightManagement(collection)

    def _get_management(self, record_type: RecordType):
        managers = {
            RecordType.CLIENT: self.client_management,
            RecordType.AIRLINE: self.airline_management,
            RecordType.FLIGHT: self.flight_management,
        }

        return managers[record_type]

    def create_record(self, record_type: RecordType, data: dict) -> None:
        manager = self._get_management(record_type)
        manager.create_record(data)

    def delete_record(self, record_type: RecordType, **criteria) -> bool:
        manager = self._get_management(record_type)
        return manager.delete_record(**criteria)

    def update_record(self, record_type: RecordType, data: dict, **criteria) -> bool:
        manager = self._get_management(record_type)
        return manager.update_record(data, **criteria)

    def search_display_record(self, record_type: RecordType, **criteria) -> dict | None:
        manager = self._get_management(record_type)
        return manager.search_display_record(**criteria)
