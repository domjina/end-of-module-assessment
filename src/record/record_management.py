"""Provide record management and persistent record collection functionality."""
from abc import ABC, abstractmethod
import dataclasses
import json
from datetime import datetime
from record.client_record import ClientRecord
from record.airline_record import AirlineRecord
from record.flight_record import FlightRecord
from record.record_types import RecordType

class RecordCollection:
    """Manage the shared collection of records and persistent storage."""
    def __init__(self, file_path: str = "src/data/records.jsonl"):
        self.records: list[dict] = []
        self.file_path = file_path
        self.load()

    def get_next_id(self, record_type: str) -> int:
        """Return the next unused ID for the specific record type."""
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
        """Add a record to the collection and save the updated data."""
        self.records.append(record)
        self.save()

    def delete(self, record_type: str | None = None, **criteria) -> bool:
        """Delete the first record matching the supplied criteria."""
        for index, record in enumerate(self.records):
            if record_type is not None and record.get("record_type") != record_type:
                continue

            if all(record.get(key) == value for key, value in criteria.items()):
                del self.records[index]
                self.save()
                return True
        return False

    def update(self, new_record: dict, **criteria) -> bool:
        """Replace the first record matching the supplied criteria."""
        for index, record in enumerate(self.records):
            if all(record.get(key) == value for key, value in criteria.items()):
                self.records[index] = new_record
                self.save()
                return True

        return False

    def find(self, record_type: str | None = None, **criteria) -> dict | None:
        """Return the first record matching the supplied criteria."""
        for record in self.records:
            if record_type is not None and record.get("record_type") != record_type:
                continue

            if all(record.get(key) == value for key, value in criteria.items()):
                return record

        return None

    def search(
                self,
                field: str,
                search_term: str,
                record_type: str | None = None
        ) -> list[dict]:
            """Return all records whose specified field matches the search term exactly."""
            matches = []
            target_type = record_type.value if hasattr(record_type, "value") else str(record_type or "")

            for record in self.records:
                rec_type = str(record.get("record_type", "")).strip().lower()
                target_clean = target_type.strip().lower()

                # If searching for flights (where record_type is "" or "flight"), 
                # allow records whose stored record_type is missing/empty OR explicitly "flight"
                if target_clean in ("", "flight"):
                    if rec_type not in ("", "none", "flight"):
                        continue
                else:
                    if rec_type != target_clean:
                        continue

                # Extract & clean field value + search term
                rec_val = str(record.get(field, "")).strip().lower()
                term = str(search_term).strip().lower()

                # Clean ISO / space date formats ("2026-09-13T00:00:00" -> "2026-09-13")
                if field == "date":
                    rec_val = rec_val.replace("t", " ").split()[0]
                    term = term.replace("t", " ").split()[0]

                # 3. Exact match only
                if rec_val == term:
                    matches.append(record)

            return matches

    def save(self) -> None:
        """Save all records to the JSONL data file."""
        with open(self.file_path, "w", encoding="utf-8") as file:
            for record in self.records:
                json.dump(
                    record,
                    file,
                    default=self._json_serializer
                )
                file.write("\n")

    def load(self) -> None:
        """Load the records from the JSONL data file."""
        try:
            with open(self.file_path, "r", encoding="utf-8") as file:
                self.records = [
                    json.loads(line)
                    for line in file
                    if line.strip()
                ]
            self._convert_types()
        except FileNotFoundError:
            self.records = []
            self.save()

    @staticmethod
    def _json_serializer(value):
        """Convert datetime values into JSON-compatible ISO strings."""
        if isinstance(value, datetime):
            return value.isoformat()
        raise TypeError(
            f"Object of type {type(value).__name__} is not JSON serializable"
        )

    def _convert_types(self) -> None:
        for record in self.records:
            if "date" in record and isinstance(record["date"], str):
                record["date"] = datetime.fromisoformat(record["date"])
            if "id" in record:
                record["id"] = int(record["id"])
            if "client_id" in record:
                record["client_id"] = int(record["client_id"])
            if "airline_id" in record:
                record["airline_id"] = int(record["airline_id"])

class RecordManagement(ABC):
    """Define the interface for record management operations."""
    @abstractmethod
    def create_record(self, data: dict) -> None:
        """Create a new record from the supplied data."""

    @abstractmethod
    def delete_record(self, **criteria) -> bool:
        """Delete a record matching the supplied criteria."""

    @abstractmethod
    def update_record(self, data: dict, **criteria) -> bool:
        """Update a record matching the supplied criteria."""

    @abstractmethod
    def search_display_record(self, **criteria) -> dict | None:
        """Find and return a record matching the supplied criteria."""

class ClientManagement(RecordManagement):
    """Manage Client records using a shared record collection."""
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
    
    def search_display_record(self, **criteria) -> list[dict] | dict | None:
        client_id = criteria.get("record_id") or criteria.get("id") or criteria.get("client_id")
        if client_id:
            return self.collection.find(
                record_type=RecordType.CLIENT.value,
                id=client_id
            )
        if criteria:
            field, search_term = next(iter(criteria.items()))
            
            return self.collection.search(
                field=field,
                search_term=str(search_term),
                record_type=RecordType.CLIENT.value
            )

        return []
    
class AirlineManagement(RecordManagement):
    """Manage Airline records using a shared record collection."""
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

    def search_display_record(self, **criteria) -> list[dict] | dict | None:
        client_id = criteria.get("record_id") or criteria.get("id") or criteria.get("client_id")
        if client_id:
            return self.collection.find(
                record_type=RecordType.AIRLINE.value,
                id=client_id
            )
        if criteria:
            field, search_term = next(iter(criteria.items()))
            
            return self.collection.search(
                field=field,
                search_term=str(search_term),
                record_type=RecordType.AIRLINE.value
            )

        return []

class FlightManagement(RecordManagement):
    """Manage Flight records using a shared record collection."""
    def __init__(self, collection: RecordCollection):
        self.collection = collection

    def create_record(self, data: dict) -> None:
        client_id = data["client_id"]
        airline_id = data["airline_id"]
        existing_flight = self.collection.find(
            client_id=client_id,
            airline_id=airline_id,
            date=data["date"],
            start_city=data["start_city"],
            end_city=data["end_city"]
        )
        if existing_flight is not None:
            raise ValueError("Flight already exists")

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
            client_id=criteria.get("client_id"),
            airline_id=criteria.get("airline_id"),
            date=criteria.get("date"),
            start_city=criteria.get("start_city"),
            end_city=criteria.get("end_city")
        )

    def update_record(self, data: dict, **criteria) -> bool:
        payload = data.copy()

        # Extract IDs from criteria or payload, popping them from payload so they aren't passed twice
        client_id = criteria.get("client_id", payload.pop("client_id", None))
        airline_id = criteria.get("airline_id", payload.pop("airline_id", None))

        flight = FlightRecord(
            client_id=client_id,
            airline_id=airline_id,
            **payload
        )
        return self.collection.update(
            dataclasses.asdict(flight),
            client_id=client_id,
            airline_id=airline_id,
            date=criteria.get("date", payload.get("date")),
            start_city=criteria.get("start_city", payload.get("start_city")),
            end_city=criteria.get("end_city", payload.get("end_city"))
        )

    def search_display_record(self, **criteria) -> list[dict] | dict | None:
            # 1. Single Flight ID lookup
            flight_id = criteria.get("record_id") or criteria.get("id") or criteria.get("flight_id")
            if flight_id:
                return self.collection.find(
                    record_type=RecordType.FLIGHT.value,
                    id=flight_id
                )

            # 2. Filter out date if another text/ID field was populated in the GUI
            non_date = {k: v for k, v in criteria.items() if k != "date" and str(v).strip() != ""}
            active = non_date if non_date else {k: v for k, v in criteria.items() if str(v).strip() != ""}

            if not active:
                return []

            # 3. Select active key (e.g. 'start_city')
            field, raw_val = next(iter(active.items()))
            search_term = str(raw_val).replace("T", " ").split()[0] if field == "date" else str(raw_val)

            # 4. Route directly to collection.search
            return self.collection.search(
                field=field,
                search_term=search_term,
                record_type=RecordType.FLIGHT.value
            )
        

class RecordManager:
    """Coordinate record operations across different record types."""
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
        """Create a record using the manager for the specified record type."""
        manager = self._get_management(record_type)
        manager.create_record(data)

    def delete_record(self, record_type: RecordType, **criteria) -> bool:
        """Delete a record using the manager for the specified record type."""
        manager = self._get_management(record_type)
        return manager.delete_record(**criteria)

    def update_record(self, record_type: RecordType, data: dict, **criteria) -> bool:
        """Update a record using the manager for the specified record type."""
        manager = self._get_management(record_type)
        return manager.update_record(data, **criteria)

    def search_display_record(self, record_type: RecordType, **criteria) -> dict | None:
        """Find a record using the manager for the specified record type."""
        manager = self._get_management(record_type)
        return manager.search_display_record(**criteria)
