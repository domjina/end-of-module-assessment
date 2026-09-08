"""Standalone record-data validation.

Pure functions with no dependency on ``RecordCollection``, persistence, file I/O
or the GUI.

``validate_client`` / ``validate_airline`` / ``validate_flight`` check the
``data`` dict supplied to create or update a record:

* every field the record kind defines must be present and of its declared type;
  ``phone_number`` and ``zip_code`` stay strings and are never coerced or
  format-checked;
* a Flight ``date`` must be a real ``datetime.datetime`` (string <-> datetime
  conversion belongs to load/save, not here);
* ``client_id`` / ``airline_id`` must be ``int`` and not ``bool``;
* ``name`` (Client) and ``company_name`` (Airline) must be non-blank after
  ``str.strip()``; no other field has a non-blank rule, so address lines,
  ``state``, ``city``, ``country``, ``zip_code``, ``phone_number`` and the Flight
  cities may be empty strings;
* a Client/Airline ``data`` dict must not contain an ``id`` key (the system
  assigns it).

``validate_stored_record`` is a separate structural check for a record read back
from the JSONL store: it identifies the kind by shape, requires the persisted
``id`` for Client/Airline, checks presence and type only, does not look at
``record_type``, and never checks whether a Flight's referenced Client/Airline
exists (so historical orphaned Flights remain valid). It does not introduce a
Flight ID or any global/unique-ID rule.
"""

from datetime import datetime


class ValidationError(ValueError):
    """Raised when record data fails structural, type or value validation."""


# Fields carried in a create/update ``data`` dict for each record kind (the
# system-assigned ``id`` and ``record_type`` are excluded).
_CLIENT_STRING_FIELDS = (
    "name",
    "address_line_1",
    "address_line_2",
    "address_line_3",
    "city",
    "state",
    "zip_code",
    "country",
    "phone_number",
)
_CLIENT_NON_BLANK = frozenset({"name"})

_AIRLINE_STRING_FIELDS = ("company_name",)
_AIRLINE_NON_BLANK = frozenset({"company_name"})

_FLIGHT_INT_FIELDS = ("client_id", "airline_id")
_FLIGHT_STRING_FIELDS = ("start_city", "end_city")


# --------------------------------------------------------------------------
# Reusable field checks
# --------------------------------------------------------------------------
def require_str(field_name: str, value, *, allow_blank: bool = True) -> None:
    """Require ``value`` to be a ``str``; optionally require it to be non-blank."""
    if not isinstance(value, str):
        raise ValidationError(
            f"{field_name}: expected a string, got {type(value).__name__}"
        )
    if not allow_blank and not value.strip():
        raise ValidationError(f"{field_name}: must not be blank")


def require_int(field_name: str, value) -> None:
    """Require ``value`` to be an ``int`` and reject ``bool``."""
    if isinstance(value, bool):
        raise ValidationError(
            f"{field_name}: expected an integer, got a boolean"
        )
    if not isinstance(value, int):
        raise ValidationError(
            f"{field_name}: expected an integer, got {type(value).__name__}"
        )


def require_datetime(field_name: str, value) -> None:
    """Require ``value`` to be a real ``datetime.datetime`` (not a date/str)."""
    if not isinstance(value, datetime):
        raise ValidationError(
            f"{field_name}: expected a datetime, got {type(value).__name__}"
        )


def _field(data: dict, field_name: str):
    if field_name not in data:
        raise ValidationError(f"{field_name}: required field is missing")
    return data[field_name]


def _reject_system_id(data: dict) -> None:
    if "id" in data:
        raise ValidationError(
            "id: assigned by the system; omit it from the record data"
        )


# --------------------------------------------------------------------------
# Public validators
# --------------------------------------------------------------------------
def validate_client(data: dict) -> None:
    """Validate a Client ``data`` dict. Raises ``ValidationError`` on failure."""
    _reject_system_id(data)
    for name in _CLIENT_STRING_FIELDS:
        require_str(
            name, _field(data, name), allow_blank=name not in _CLIENT_NON_BLANK
        )


def validate_airline(data: dict) -> None:
    """Validate an Airline ``data`` dict. Raises ``ValidationError`` on failure."""
    _reject_system_id(data)
    for name in _AIRLINE_STRING_FIELDS:
        require_str(
            name, _field(data, name), allow_blank=name not in _AIRLINE_NON_BLANK
        )


def validate_flight(data: dict) -> None:
    """Validate a Flight ``data`` dict. Raises ``ValidationError`` on failure."""
    for name in _FLIGHT_INT_FIELDS:
        require_int(name, _field(data, name))
    require_datetime("date", _field(data, "date"))
    for name in _FLIGHT_STRING_FIELDS:
        require_str(name, _field(data, name))


# --------------------------------------------------------------------------
# Stored-record structural validation (used by RecordCollection.load)
# --------------------------------------------------------------------------
# A persisted record legitimately carries the system-assigned ``id`` (Client /
# Airline) that the create-input validators above reject. Record kind is
# identified by structure only -- ``record_type`` is never read, assigned or
# enforced -- and only presence and type are checked (no non-blank rules, no
# reference-existence checks).

_STORED_CLIENT_FIELDS = {
    "id": require_int,
    "name": require_str,
    "address_line_1": require_str,
    "address_line_2": require_str,
    "address_line_3": require_str,
    "city": require_str,
    "state": require_str,
    "zip_code": require_str,
    "country": require_str,
    "phone_number": require_str,
}
_STORED_AIRLINE_FIELDS = {
    "id": require_int,
    "company_name": require_str,
}
_STORED_FLIGHT_FIELDS = {
    "client_id": require_int,
    "airline_id": require_int,
    "date": require_datetime,
    "start_city": require_str,
    "end_city": require_str,
}
# Allowed on a stored row structurally without being validated here.
_STORED_OPTIONAL_KEYS = frozenset({"record_type"})

_STORED_SPECS = {
    "Client": _STORED_CLIENT_FIELDS,
    "Airline": _STORED_AIRLINE_FIELDS,
    "Flight": _STORED_FLIGHT_FIELDS,
}


def validate_stored_record(record: dict) -> None:
    """Structurally validate one record read back from the JSONL store.

    The record kind is identified by its fields (a Client has ``name``, an
    Airline has ``company_name``, a Flight has ``client_id`` / ``airline_id``) --
    never by ``record_type``. For the identified kind every field must be present
    and of the right type; a persisted ``id`` is required and must be a real
    ``int`` (``bool`` rejected). Purely structural: no non-blank rules, no
    ``record_type`` handling, and no check of whether a Flight's referenced
    Client / Airline still exists (historical orphaned Flights stay loadable).
    Raises ``ValidationError`` for an unknown, incomplete or ambiguous shape.
    """
    if not isinstance(record, dict):
        raise ValidationError(
            f"expected a record object, got {type(record).__name__}"
        )

    keys = set(record)
    matched = [
        kind for kind, present in (
            ("Client", "name" in keys),
            ("Airline", "company_name" in keys),
            ("Flight", "client_id" in keys or "airline_id" in keys),
        ) if present
    ]
    if len(matched) > 1:
        raise ValidationError(
            f"ambiguous record structure: looks like {' and '.join(matched)}"
        )
    if not matched:
        raise ValidationError(
            f"unrecognised record structure with fields {sorted(keys)}"
        )

    kind = matched[0]
    spec = _STORED_SPECS[kind]

    missing = sorted(set(spec) - keys)
    if missing:
        raise ValidationError(f"incomplete {kind} record: missing {missing}")
    unexpected = sorted(keys - set(spec) - _STORED_OPTIONAL_KEYS)
    if unexpected:
        raise ValidationError(
            f"unexpected field(s) for a {kind} record: {unexpected}"
        )
    for field_name, check in spec.items():
        check(field_name, record[field_name])
