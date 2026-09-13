"""Tests for the standalone validators.

Every test calls ``validate_client`` / ``validate_airline`` / ``validate_flight``
/ ``validate_stored_record`` (or the ``require_*`` helpers) directly. Nothing
here imports ``RecordCollection`` or any Management class; the validator module
must stay standalone.

Run from the repository root (Python >= 3.11)::

    python -m unittest tests.test_nhi_validation -v
"""

from __future__ import annotations

import unittest
from datetime import date, datetime
from pathlib import Path

from src.record import validation
from src.record.validation import (
    ValidationError,
    require_datetime,
    require_int,
    require_str,
    validate_airline,
    validate_client,
    validate_flight,
    validate_stored_record,
)

GOOD_CLIENT = {
    "record_type": "client",  # present; validator must ignore it entirely
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
GOOD_AIRLINE = {"record_type": "airline", "company_name": "Test Airways"}
GOOD_FLIGHT = {
    "client_id": 1,
    "airline_id": 2,
    "date": datetime(2026, 9, 10, 14, 30),
    "start_city": "London",
    "end_city": "New York",
}


class RequireHelpers(unittest.TestCase):
    def test_require_int_accepts_any_int_including_zero_and_negative(self) -> None:
        for value in (0, 1, 42, -7):
            require_int("client_id", value)  # must not raise

    def test_require_int_rejects_bool(self) -> None:
        for value in (True, False):
            with self.assertRaises(ValidationError) as ctx:
                require_int("client_id", value)
            self.assertIn("boolean", str(ctx.exception))

    def test_require_int_rejects_float_and_str_and_none(self) -> None:
        for value in (1.0, "1", None):
            with self.assertRaises(ValidationError):
                require_int("airline_id", value)

    def test_require_str_rejects_non_strings(self) -> None:
        for value in (123, None, True, b"bytes", ["x"]):
            with self.assertRaises(ValidationError):
                require_str("name", value)

    def test_require_str_allows_blank_by_default(self) -> None:
        require_str("address_line_2", "")
        require_str("state", "   ")

    def test_require_str_rejects_blank_when_disallowed(self) -> None:
        for value in ("", "   ", "\t\n"):
            with self.assertRaises(ValidationError) as ctx:
                require_str("name", value, allow_blank=False)
            self.assertIn("blank", str(ctx.exception))

    def test_require_datetime(self) -> None:
        require_datetime("date", datetime(2026, 1, 1, 9, 0))  # ok
        for value in ("2026-01-01T09:00:00", date(2026, 1, 1), 1_700_000_000, None):
            with self.assertRaises(ValidationError) as ctx:
                require_datetime("date", value)
            self.assertIn("datetime", str(ctx.exception))


class ValidateClient(unittest.TestCase):
    def test_good_client_passes_and_returns_none(self) -> None:
        self.assertIsNone(validate_client(dict(GOOD_CLIENT)))

    def test_missing_required_field_raises_naming_it(self) -> None:
        for field in (
            "name", "address_line_1", "address_line_2", "address_line_3",
            "city", "state", "zip_code", "country", "phone_number",
        ):
            with self.subTest(missing=field):
                data = {k: v for k, v in GOOD_CLIENT.items() if k != field}
                with self.assertRaises(ValidationError) as ctx:
                    validate_client(data)
                self.assertIn(field, str(ctx.exception))
                self.assertIn("missing", str(ctx.exception))

    def test_name_must_not_be_blank(self) -> None:
        for blank in ("", "   "):
            with self.assertRaises(ValidationError) as ctx:
                validate_client({**GOOD_CLIENT, "name": blank})
            self.assertIn("blank", str(ctx.exception))

    def test_optional_string_fields_may_be_blank(self) -> None:
        allblank = {
            **GOOD_CLIENT,
            "address_line_1": "", "address_line_2": "", "address_line_3": "",
            "city": "", "state": "", "zip_code": "", "country": "",
            "phone_number": "",
        }
        self.assertIsNone(validate_client(allblank))  # only 'name' is required non-blank

    def test_non_string_field_raises(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            validate_client({**GOOD_CLIENT, "city": 123})
        self.assertIn("expected a string", str(ctx.exception))

    def test_system_id_key_is_rejected(self) -> None:
        for value in (1, 0, True, "1", None):
            with self.assertRaises(ValidationError) as ctx:
                validate_client({**GOOD_CLIENT, "id": value})
            self.assertIn("id", str(ctx.exception))
            self.assertIn("system", str(ctx.exception))

    def test_record_type_is_neither_required_nor_validated(self) -> None:
        without = {k: v for k, v in GOOD_CLIENT.items() if k != "record_type"}
        self.assertIsNone(validate_client(without))
        self.assertIsNone(validate_client({**GOOD_CLIENT, "record_type": "anything"}))
        self.assertIsNone(validate_client({**GOOD_CLIENT, "record_type": 999}))

    def test_phone_and_zip_are_kept_as_strings_and_not_mutated(self) -> None:
        data = {**GOOD_CLIENT, "phone_number": "01234567890", "zip_code": "0000123"}
        snapshot = dict(data)
        validate_client(data)
        self.assertEqual(data, snapshot)
        self.assertIsInstance(data["phone_number"], str)
        self.assertIsInstance(data["zip_code"], str)
        self.assertEqual(data["zip_code"], "0000123")

    def test_unexpected_keys_other_than_id_are_left_to_the_dataclass(self) -> None:
        # This validator checks the documented rules only; unknown-key rejection
        # is left to the frozen dataclass constructor.
        self.assertIsNone(validate_client({**GOOD_CLIENT, "middle_name": "Q"}))


class ValidateAirline(unittest.TestCase):
    def test_good_airline_passes(self) -> None:
        self.assertIsNone(validate_airline(dict(GOOD_AIRLINE)))

    def test_missing_company_name_raises(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            validate_airline({"record_type": "airline"})
        self.assertIn("company_name", str(ctx.exception))

    def test_company_name_must_not_be_blank(self) -> None:
        for blank in ("", "   "):
            with self.assertRaises(ValidationError):
                validate_airline({**GOOD_AIRLINE, "company_name": blank})

    def test_non_string_company_name_raises(self) -> None:
        with self.assertRaises(ValidationError):
            validate_airline({**GOOD_AIRLINE, "company_name": 42})

    def test_system_id_key_is_rejected(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            validate_airline({**GOOD_AIRLINE, "id": 1})
        self.assertIn("system", str(ctx.exception))

    def test_record_type_not_validated(self) -> None:
        self.assertIsNone(validate_airline({"company_name": "X"}))
        self.assertIsNone(validate_airline({**GOOD_AIRLINE, "record_type": "whatever"}))


class ValidateFlight(unittest.TestCase):
    def test_good_flight_passes(self) -> None:
        self.assertIsNone(validate_flight(dict(GOOD_FLIGHT)))

    def test_missing_field_raises_naming_it(self) -> None:
        for field in ("client_id", "airline_id", "date", "start_city", "end_city"):
            with self.subTest(missing=field):
                data = {k: v for k, v in GOOD_FLIGHT.items() if k != field}
                with self.assertRaises(ValidationError) as ctx:
                    validate_flight(data)
                self.assertIn(field, str(ctx.exception))

    def test_client_and_airline_ids_must_be_integers(self) -> None:
        for field in ("client_id", "airline_id"):
            with self.subTest(field=field):
                with self.assertRaises(ValidationError) as ctx:
                    validate_flight({**GOOD_FLIGHT, field: "1"})
                self.assertIn("expected an integer", str(ctx.exception))

    def test_boolean_ids_are_rejected(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            validate_flight({**GOOD_FLIGHT, "client_id": True})
        self.assertIn("boolean", str(ctx.exception))
        with self.assertRaises(ValidationError):
            validate_flight({**GOOD_FLIGHT, "airline_id": False})

    def test_date_must_be_a_real_datetime(self) -> None:
        for value in ("2026-09-10T14:30:00", date(2026, 9, 10), None, 1_700_000_000):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError) as ctx:
                    validate_flight({**GOOD_FLIGHT, "date": value})
                self.assertIn("datetime", str(ctx.exception))

    def test_valid_datetime_passes(self) -> None:
        self.assertIsNone(
            validate_flight({**GOOD_FLIGHT, "date": datetime(2030, 1, 1)})
        )

    def test_cities_must_be_strings_but_may_be_blank(self) -> None:
        self.assertIsNone(
            validate_flight({**GOOD_FLIGHT, "start_city": "", "end_city": ""})
        )
        with self.assertRaises(ValidationError):
            validate_flight({**GOOD_FLIGHT, "start_city": 5})

    def test_no_reference_existence_check(self) -> None:
        # Non-existent Client/Airline IDs are structurally valid here; checking
        # that the referenced records exist is done elsewhere, not by this
        # validator.
        self.assertIsNone(
            validate_flight({**GOOD_FLIGHT, "client_id": 999999, "airline_id": 888888})
        )

    def test_flight_id_is_not_required_and_not_introduced(self) -> None:
        self.assertNotIn("id", GOOD_FLIGHT)
        self.assertIsNone(validate_flight(dict(GOOD_FLIGHT)))  # no 'id' needed


class ValidatorProperties(unittest.TestCase):
    def test_all_validators_return_none_on_success(self) -> None:
        self.assertIsNone(validate_client(dict(GOOD_CLIENT)))
        self.assertIsNone(validate_airline(dict(GOOD_AIRLINE)))
        self.assertIsNone(validate_flight(dict(GOOD_FLIGHT)))

    def test_validators_do_not_mutate_their_input(self) -> None:
        for validator, good in (
            (validate_client, GOOD_CLIENT),
            (validate_airline, GOOD_AIRLINE),
            (validate_flight, GOOD_FLIGHT),
        ):
            with self.subTest(validator=validator.__name__):
                data = dict(good)
                validator(data)
                self.assertEqual(data, good)

    def test_validation_error_is_a_valueerror(self) -> None:
        self.assertTrue(issubclass(ValidationError, ValueError))

    def test_module_is_standalone(self) -> None:
        import ast

        source = Path(validation.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        self.assertEqual(
            imported, {"datetime"},
            f"validation.py must import only stdlib datetime, got {imported}",
        )
        for leaked in ("RecordCollection", "RecordManager", "PersistenceError",
                       "record_management"):
            self.assertFalse(
                hasattr(validation, leaked),
                f"validation.py must not expose {leaked}",
            )


# --------------------------------------------------------------------------
# validate_stored_record — structural check for rows read from the store
# --------------------------------------------------------------------------
STORED_CLIENT = {
    "id": 1,
    "record_type": "client",  # present in stored rows; must NOT be validated
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
STORED_AIRLINE = {"id": 1, "record_type": "airline", "company_name": "Test Airways"}
STORED_FLIGHT = {
    "client_id": 1,
    "airline_id": 2,
    "date": datetime(2026, 9, 10, 14, 30),
    "start_city": "London",
    "end_city": "New York",
}
_CLIENT_CORE = [
    "id", "name", "address_line_1", "address_line_2", "address_line_3",
    "city", "state", "zip_code", "country", "phone_number",
]


class ValidateStoredRecord(unittest.TestCase):
    def test_valid_stored_rows_pass_and_return_none(self) -> None:
        self.assertIsNone(validate_stored_record(dict(STORED_CLIENT)))
        self.assertIsNone(validate_stored_record(dict(STORED_AIRLINE)))
        self.assertIsNone(validate_stored_record(dict(STORED_FLIGHT)))

    def test_persisted_id_is_accepted_not_rejected(self) -> None:
        # The create-input rule (_reject_system_id) must NOT apply to stored rows.
        self.assertIsNone(validate_stored_record({**STORED_CLIENT, "id": 5}))
        self.assertIsNone(validate_stored_record({**STORED_AIRLINE, "id": 12}))

    def test_kind_is_identified_without_record_type(self) -> None:
        self.assertIsNone(
            validate_stored_record({k: v for k, v in STORED_CLIENT.items()
                                    if k != "record_type"})
        )
        self.assertIsNone(
            validate_stored_record({k: v for k, v in STORED_AIRLINE.items()
                                    if k != "record_type"})
        )
        # record_type value is never inspected.
        self.assertIsNone(validate_stored_record({**STORED_CLIENT, "record_type": "nonsense"}))
        self.assertIsNone(validate_stored_record({**STORED_CLIENT, "record_type": 999}))

    def test_stored_client_missing_field_raises(self) -> None:
        for field in _CLIENT_CORE:
            with self.subTest(missing=field):
                row = {k: v for k, v in STORED_CLIENT.items() if k != field}
                with self.assertRaises(ValidationError) as ctx:
                    validate_stored_record(row)
                if field == "name":
                    # 'name' is the Client discriminator: without it the shape
                    # cannot be identified at all.
                    self.assertIn("unrecognised", str(ctx.exception))
                else:
                    self.assertIn("incomplete Client", str(ctx.exception))
                    self.assertIn(field, str(ctx.exception))

    def test_stored_client_wrong_type_raises(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            validate_stored_record({**STORED_CLIENT, "city": 5})
        self.assertIn("expected a string", str(ctx.exception))

    def test_stored_client_unexpected_field_raises(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            validate_stored_record({**STORED_CLIENT, "middle_name": "Q"})
        self.assertIn("unexpected field", str(ctx.exception))
        self.assertIn("middle_name", str(ctx.exception))

    def test_stored_id_must_be_int_and_not_bool(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            validate_stored_record({**STORED_CLIENT, "id": True})
        self.assertIn("boolean", str(ctx.exception))
        with self.assertRaises(ValidationError):
            validate_stored_record({**STORED_AIRLINE, "id": False})
        with self.assertRaises(ValidationError) as ctx:
            validate_stored_record({**STORED_CLIENT, "id": "1"})
        self.assertIn("expected an integer", str(ctx.exception))

    def test_stored_airline_incomplete_and_unexpected(self) -> None:
        # Has the 'company_name' discriminator but is missing 'id'.
        with self.assertRaises(ValidationError) as ctx:
            validate_stored_record({"record_type": "airline", "company_name": "X"})
        self.assertIn("incomplete Airline", str(ctx.exception))
        self.assertIn("id", str(ctx.exception))
        # No discriminator at all -> unrecognised.
        with self.assertRaises(ValidationError) as ctx:
            validate_stored_record({"id": 1, "record_type": "airline"})
        self.assertIn("unrecognised", str(ctx.exception))
        # Extra field on an otherwise-complete Airline.
        with self.assertRaises(ValidationError) as ctx:
            validate_stored_record({**STORED_AIRLINE, "iata": "BA"})
        self.assertIn("unexpected field", str(ctx.exception))

    def test_stored_flight_without_id_or_record_type_is_valid(self) -> None:
        self.assertNotIn("id", STORED_FLIGHT)
        self.assertNotIn("record_type", STORED_FLIGHT)
        self.assertIsNone(validate_stored_record(dict(STORED_FLIGHT)))
        # a stray record_type on a Flight row is tolerated and ignored
        self.assertIsNone(validate_stored_record({**STORED_FLIGHT, "record_type": "flight"}))

    def test_stored_flight_missing_field_is_incomplete(self) -> None:
        for field in ("client_id", "airline_id", "date", "start_city", "end_city"):
            with self.subTest(missing=field):
                row = {k: v for k, v in STORED_FLIGHT.items() if k != field}
                with self.assertRaises(ValidationError) as ctx:
                    validate_stored_record(row)
                self.assertIn(field, str(ctx.exception))

    def test_stored_flight_ids_must_be_int_not_bool(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            validate_stored_record({**STORED_FLIGHT, "client_id": True})
        self.assertIn("boolean", str(ctx.exception))
        with self.assertRaises(ValidationError) as ctx:
            validate_stored_record({**STORED_FLIGHT, "airline_id": "2"})
        self.assertIn("expected an integer", str(ctx.exception))

    def test_stored_flight_date_must_be_a_datetime(self) -> None:
        for value in ("2026-09-10T14:30:00", date(2026, 9, 10), None, 1_700_000_000):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError) as ctx:
                    validate_stored_record({**STORED_FLIGHT, "date": value})
                self.assertIn("datetime", str(ctx.exception))

    def test_orphaned_flight_is_structurally_valid(self) -> None:
        # No collection is consulted; a Flight referencing non-existent ids is fine.
        self.assertIsNone(
            validate_stored_record(
                {**STORED_FLIGHT, "client_id": 999999, "airline_id": 888888}
            )
        )

    def test_ambiguous_structure_raises(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            validate_stored_record({**STORED_CLIENT, "company_name": "X"})
        self.assertIn("ambiguous", str(ctx.exception))
        with self.assertRaises(ValidationError) as ctx:
            validate_stored_record({**STORED_FLIGHT, "name": "Someone"})
        self.assertIn("ambiguous", str(ctx.exception))

    def test_unrecognised_structure_raises(self) -> None:
        for row in ({}, {"id": 1, "record_type": "client"}, {"foo": "bar"}):
            with self.subTest(row=row):
                with self.assertRaises(ValidationError) as ctx:
                    validate_stored_record(row)
                self.assertIn("unrecognised", str(ctx.exception))

    def test_non_dict_raises(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            validate_stored_record([1, 2, 3])
        self.assertIn("record object", str(ctx.exception))

    def test_does_not_mutate_input(self) -> None:
        for row in (STORED_CLIENT, STORED_AIRLINE, STORED_FLIGHT):
            data = dict(row)
            validate_stored_record(data)
            self.assertEqual(data, row)


if __name__ == "__main__":
    unittest.main(verbosity=2)
