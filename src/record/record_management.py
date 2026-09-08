from abc import ABC, abstractmethod
import dataclasses
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from src.record.client_record import ClientRecord
from src.record.airline_record import AirlineRecord
from src.record.flight_record import FlightRecord
from src.record.record_types import RecordType
from src.record.validation import ValidationError, validate_stored_record

class PersistenceError(Exception):
    """Raised when records cannot be loaded from / saved to the file system.

    Messages include the file path and, for a malformed line, its 1-based
    physical line number so the stored file can be corrected.
    """

class RecordCollection:
    def __init__(self, file_path: str = "src/data/records.jsonl"):
        self.records: list[dict] = []
        self.file_path = file_path
        self.load()

    def get_next_id(self, record_class: type) -> int:
        field_names = {
            field.name
            for field in dataclasses.fields(record_class)
        }

        matching_records = [
            record
            for record in self.records
            if field_names.issubset(record.keys())
        ]

        return max(
            (record["id"] for record in matching_records),
            default=0
        ) + 1

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
        self._commit(lambda: self.records.append(record))

    def delete(self, **criteria) -> bool:
        for index, record in enumerate(self.records):
            if all(record.get(key) == value for key, value in criteria.items()):
                self._commit(lambda index=index: self.records.pop(index))
                return True

        return False

    def update(self, new_record: dict, **criteria) -> bool:
        for index, record in enumerate(self.records):
            if all(record.get(key) == value for key, value in criteria.items()):
                self._commit(
                    lambda index=index: self.records.__setitem__(index, new_record)
                )
                return True

        return False

    def find(self, **criteria) -> dict | None:
        for record in self.records:
            if all(record.get(key) == value for key, value in criteria.items()):
                return record
        return None

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
        next_id = self.collection.get_next_id(ClientRecord)
        client = ClientRecord(id=next_id, **data)
        self.collection.add(dataclasses.asdict(client))

    def delete_record(self, **criteria) -> bool:
        return self.collection.delete(
            id=criteria["record_id"]
        )

    def update_record(self, data: dict, **criteria) -> bool:
        record_id = criteria["record_id"]

        client = ClientRecord(
            id=record_id,
            **data
        )

        return self.collection.update(
            dataclasses.asdict(client),
            id=record_id
        )

    def search_display_record(self, **criteria) -> dict | None:
        return self.collection.find(
            id=criteria["record_id"]
        )

class AirlineManagement(RecordManagement):
    def __init__(self, collection: RecordCollection):
        self.collection = collection

    def create_record(self, data: dict) -> None:
        next_id = self.collection.get_next_id(AirlineRecord)
        airline = AirlineRecord(id=next_id, **data)
        self.collection.add(dataclasses.asdict(airline))

    def delete_record(self, **criteria) -> bool:
        return self.collection.delete(
            id=criteria["record_id"]
        )

    def update_record(self, data: dict, **criteria) -> bool:
        record_id = criteria["record_id"]
        airline = AirlineRecord(
            id=record_id,
            **data
        )
        return self.collection.update(
            dataclasses.asdict(airline),
            id=record_id
        )

    def search_display_record(self, **criteria) -> dict | None:
        return self.collection.find(
            id=criteria["record_id"]
        )

class FlightManagement(RecordManagement):
    def __init__(self, collection: RecordCollection):
        self.collection = collection

    def create_record(self, data: dict) -> None:
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
