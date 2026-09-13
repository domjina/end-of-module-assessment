"""Provide record management and persistent record collection functionality."""
from abc import ABC, abstractmethod
import dataclasses
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from record.client_record import ClientRecord
from record.airline_record import AirlineRecord
from record.flight_record import FlightRecord
from record.record_types import RecordType
from record.validation import ValidationError, validate_stored_record
from record.validation import (
    validate_client,
    validate_airline,
    validate_flight
)

class PersistenceError(Exception):
    """Raised when records cannot be loaded from / saved to the file system.

    Messages include the file path and, for a malformed line, its 1-based
    physical line number so the stored file can be corrected.
    """

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

    def _commit(self, mutate) -> None:
        """Apply ``mutate()`` to ``self.records`` and persist the result.

        If ``save()`` fails, ``self.records`` is restored to its exact
        pre-operation contents and the ``PersistenceError`` is re-raised, so the
        in-memory list and the file on disk never disagree.
        """
        snapshot = list(self.records)
        mutate()
        try:
            self.save()
        except PersistenceError:
            self.records = snapshot
            raise

    def add(self, record: dict) -> None:
        """Add a record to the collection and save the updated data."""
        self._commit(lambda: self.records.append(record))

    def delete(self, record_type: str | None = None, **criteria) -> bool:
        """Delete the first record matching the supplied criteria."""
        for index, record in enumerate(self.records):
            if record_type is not None and record.get("record_type") != record_type:
                continue

            if all(record.get(key) == value for key, value in criteria.items()):
                self._commit(lambda index=index: self.records.pop(index))
                return True
        return False

    def update(self, new_record: dict, **criteria) -> bool:
        """Replace the first record matching the supplied criteria."""
        for index, record in enumerate(self.records):
            if all(record.get(key) == value for key, value in criteria.items()):
                self._commit(
                    lambda index=index: self.records.__setitem__(index, new_record)
                )
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
        """Write ``self.records`` to ``self.file_path`` atomically.

        The records are serialised up front, written to a temporary file in the
        destination directory and closed, and only then moved into place with
        ``os.replace``. If serialisation, writing or the replacement fails, the
        previous destination file is left untouched, the temporary file is
        removed (without hiding the original error), and a ``PersistenceError``
        naming the destination and the failed operation is raised.
        """
        destination = self.file_path
        directory = Path(destination).parent

        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise PersistenceError(
                f"cannot save {destination}: creating its directory failed: {exc}"
            ) from exc

        try:
            payload = "".join(
                json.dumps(record, default=self._json_serializer) + "\n"
                for record in self.records
            )
        except TypeError as exc:
            raise PersistenceError(
                f"cannot save {destination}: serialising the records failed: {exc}"
            ) from exc

        try:
            handle, temp_path = tempfile.mkstemp(
                dir=directory,
                prefix=Path(destination).name + ".",
                suffix=".tmp",
            )
        except OSError as exc:
            raise PersistenceError(
                f"cannot save {destination}: creating a temporary file failed: {exc}"
            ) from exc
        os.close(handle)

        try:
            try:
                with open(temp_path, "w", encoding="utf-8") as temp_file:
                    temp_file.write(payload)
            except OSError as exc:
                raise PersistenceError(
                    f"cannot save {destination}: writing the temporary file failed: {exc}"
                ) from exc

            try:
                os.replace(temp_path, destination)
            except OSError as exc:
                raise PersistenceError(
                    f"cannot save {destination}: replacing the destination file failed: {exc}"
                ) from exc
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    def load(self) -> None:
        """Load records from ``self.file_path`` into ``self.records``.

        The whole file is parsed into a temporary list first; ``self.records``
        is replaced only once every non-blank line has been read as a JSON
        object with a parseable ``date`` (when present) and a recognised record
        structure. On any failure a ``PersistenceError`` naming the file and the
        1-based physical line is raised and both the file on disk and the
        current in-memory list are left unchanged. A missing file is treated as
        an empty store and created.
        """
        try:
            Path(self.file_path).parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise PersistenceError(
                f"cannot create storage directory for {self.file_path}: {exc}"
            ) from exc

        try:
            file = open(self.file_path, "r", encoding="utf-8")
        except FileNotFoundError:
            self.records = []
            self.save()
            return
        except OSError as exc:
            raise PersistenceError(
                f"cannot read {self.file_path}: {exc}"
            ) from exc

        parsed: list[dict] = []
        with file:
            for line_number, line in enumerate(file, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise PersistenceError(
                        f"{self.file_path}:{line_number}: invalid JSON: {exc.msg}"
                    ) from exc
                if not isinstance(record, dict):
                    raise PersistenceError(
                        f"{self.file_path}:{line_number}: expected a JSON object, "
                        f"got {type(record).__name__}"
                    )
                if isinstance(record.get("date"), str):
                    try:
                        record["date"] = datetime.fromisoformat(record["date"])
                    except ValueError as exc:
                        raise PersistenceError(
                            f"{self.file_path}:{line_number}: invalid date "
                            f"{record['date']!r}"
                        ) from exc
                try:
                    validate_stored_record(record)
                except ValidationError as exc:
                    raise PersistenceError(
                        f"{self.file_path}:{line_number}: {exc}"
                    ) from exc
                parsed.append(record)

        self.records = parsed

    @staticmethod
    def _json_serializer(value):
        """Convert datetime values into JSON-compatible ISO strings."""
        if isinstance(value, datetime):
            return value.isoformat()
        raise TypeError(
            f"Object of type {type(value).__name__} is not JSON serializable"
        )

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
        validate_client(data)

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
        validate_client(data)
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
        validate_airline(data)
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
        validate_airline(data)
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
        validate_flight(data)
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

        current_flight = self.collection.find(
            client_id=criteria["client_id"],
            airline_id=criteria["airline_id"],
            date=criteria["date"],
            start_city=criteria["start_city"],
            end_city=criteria["end_city"]
        )

        if current_flight is None:
            return False

        proposed_flight = {
            "client_id": client_id,
            "airline_id": airline_id,
            **data
        }

        validate_flight(proposed_flight)

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

        duplicate = self.collection.find(
            client_id=proposed_flight["client_id"],
            airline_id=proposed_flight["airline_id"],
            date=proposed_flight["date"],
            start_city=proposed_flight["start_city"],
            end_city=proposed_flight["end_city"]
        )

        if duplicate is not None and duplicate is not current_flight:
            raise ValueError("Flight already exists")

        flight = FlightRecord(**proposed_flight)

        return self.collection.update(
            dataclasses.asdict(flight),
            client_id=client_id,
            airline_id=airline_id,
            date=criteria.get("date", data.get("date")),
            start_city=criteria.get("start_city", data.get("start_city")),
            end_city=criteria.get("end_city", data.get("end_city"))
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
