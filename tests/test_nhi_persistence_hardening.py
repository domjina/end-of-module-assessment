"""Tests for RecordCollection persistence hardening.

``LoadHardening`` covers ``load()``:

* the parent storage directory is handled safely on first run;
* every non-blank JSONL line is parsed into a temporary list;
* malformed JSON, a non-object row and an invalid stored ``date`` each raise a
  ``PersistenceError`` whose message contains the file path and the physical
  1-based line number;
* ``self.records`` is replaced only after the whole file has loaded;
* a failed load leaves the previous in-memory list and the file bytes unchanged.

``SaveHardening`` covers atomic ``save()`` and the ``_commit`` rollback:

* successful save + reload round-trip;
* serialisation / write / replace failures each raise a ``PersistenceError``
  naming the destination and failed operation, leave the previous file intact,
  and clean up the temporary file without masking the original error;
* ``add`` / ``update`` / ``delete`` restore the exact pre-operation in-memory
  state when saving fails, and a no-match ``update`` / ``delete`` still returns
  ``False`` without saving.

All data lives in ``tempfile`` directories; the real
``src/data/records.jsonl`` is never created or touched.

Run from the repository root (Python >= 3.11)::

    python -m unittest tests.test_nhi_persistence_hardening -v
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from datetime import datetime
from unittest.mock import mock_open, patch

from src.record.record_management import PersistenceError, RecordCollection

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL_DATA_FILE = os.path.join(REPO_ROOT, "src", "data", "records.jsonl")

CLIENT_ROW = {
    "id": 1,
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
AIRLINE_ROW = {"id": 1, "record_type": "airline", "company_name": "Test Airways"}
FLIGHT_ROW = {
    "client_id": 1,
    "airline_id": 1,
    "date": "2026-09-10T14:30:00",
    "start_city": "London",
    "end_city": "New York",
}


class LoadHardening(unittest.TestCase):
    def setUp(self) -> None:
        self._real_data_existed = os.path.exists(REAL_DATA_FILE)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "records.jsonl")

    def tearDown(self) -> None:
        self.assertEqual(
            os.path.exists(REAL_DATA_FILE),
            self._real_data_existed,
            "a test touched the real src/data/records.jsonl",
        )

    # ---- helpers ------------------------------------------------------------
    def _write(self, text: str, path: str | None = None) -> str:
        path = path or self.path
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def _write_rows(self, rows, path: str | None = None) -> str:
        return self._write("".join(json.dumps(r) + "\n" for r in rows), path)

    def _bytes(self, path: str | None = None) -> bytes:
        with open(path or self.path, "rb") as fh:
            return fh.read()

    # ---- first-run / directory handling ----------------------------------
    def test_missing_file_creates_empty_store(self) -> None:
        col = RecordCollection(self.path)
        self.assertEqual(col.records, [])
        self.assertTrue(os.path.exists(self.path))
        self.assertEqual(os.path.getsize(self.path), 0)

    def test_missing_parent_directory_is_created_on_first_run(self) -> None:
        nested = os.path.join(self.tmp.name, "does", "not", "exist", "records.jsonl")
        col = RecordCollection(nested)  # must not raise
        self.assertEqual(col.records, [])
        self.assertTrue(os.path.isdir(os.path.dirname(nested)))
        self.assertTrue(os.path.exists(nested))

    def test_bare_filename_parent_is_handled(self) -> None:
        # Path("records.jsonl").parent == Path(".") — mkdir must be a safe no-op.
        cwd = os.getcwd()
        os.chdir(self.tmp.name)
        self.addCleanup(os.chdir, cwd)
        col = RecordCollection("records.jsonl")
        self.assertEqual(col.records, [])

    # ---- well-formed content -------------------------------------------------
    def test_empty_and_blank_only_files_load_empty_without_rewrite(self) -> None:
        for label, text in (("empty", ""), ("blank-lines", "\n   \n\t\n")):
            with self.subTest(file=label):
                self._write(text)
                before = self._bytes()
                col = RecordCollection(self.path)
                self.assertEqual(col.records, [])
                self.assertEqual(self._bytes(), before, "load() rewrote the file")

    def test_valid_mixed_jsonl_loads_and_converts_date(self) -> None:
        self._write_rows([CLIENT_ROW, AIRLINE_ROW, FLIGHT_ROW])
        col = RecordCollection(self.path)
        self.assertEqual(len(col.records), 3)
        flight = next(r for r in col.records if "start_city" in r)
        self.assertIsInstance(flight["date"], datetime)
        self.assertEqual(flight["date"], datetime(2026, 9, 10, 14, 30))
        client = next(r for r in col.records if r.get("record_type") == "client")
        self.assertEqual(client["name"], "Alice Example")

    # ---- malformed content: clear error with file:line ------------------
    def test_malformed_json_line_raises_with_path_and_physical_line(self) -> None:
        self._write(
            json.dumps(AIRLINE_ROW) + "\n"
            + "{ this is not valid json\n"
            + json.dumps({"id": 2, "record_type": "airline", "company_name": "B"}) + "\n"
        )
        before = self._bytes()
        with self.assertRaises(PersistenceError) as ctx:
            RecordCollection(self.path)
        msg = str(ctx.exception)
        self.assertIn(self.path, msg)
        self.assertIn(f"{self.path}:2:", msg)
        self.assertIn("invalid JSON", msg)
        self.assertEqual(self._bytes(), before, "failed load rewrote the file")

    def test_non_object_row_raises_with_path_and_line(self) -> None:
        for label, bad in (("array", "[1, 2, 3]"), ("scalar", "42"), ("string", '"x"')):
            with self.subTest(kind=label):
                self._write(json.dumps(CLIENT_ROW) + "\n" + bad + "\n")
                before = self._bytes()
                with self.assertRaises(PersistenceError) as ctx:
                    RecordCollection(self.path)
                msg = str(ctx.exception)
                self.assertIn(f"{self.path}:2:", msg)
                self.assertIn("expected a JSON object", msg)
                self.assertEqual(self._bytes(), before)

    def test_invalid_stored_date_raises_with_path_and_line(self) -> None:
        self._write(
            json.dumps(CLIENT_ROW) + "\n"
            + json.dumps({**FLIGHT_ROW, "date": "not-a-real-date"}) + "\n"
        )
        before = self._bytes()
        with self.assertRaises(PersistenceError) as ctx:
            RecordCollection(self.path)
        msg = str(ctx.exception)
        self.assertIn(f"{self.path}:2:", msg)
        self.assertIn("invalid date", msg)
        self.assertEqual(self._bytes(), before)

    def test_line_numbers_are_physical_and_count_blank_lines(self) -> None:
        self._write(
            json.dumps(AIRLINE_ROW) + "\n"   # line 1
            + "\n"                            # line 2 (blank, skipped but counted)
            + "{bad\n"                        # line 3 -> error here
        )
        with self.assertRaises(PersistenceError) as ctx:
            RecordCollection(self.path)
        self.assertIn(f"{self.path}:3:", str(ctx.exception))

    # ---- temp-list swap: state preserved on failure -------------------------
    def test_reload_over_corrupt_file_keeps_previous_in_memory_records(self) -> None:
        self._write_rows([CLIENT_ROW, AIRLINE_ROW])
        col = RecordCollection(self.path)
        good = [dict(r) for r in col.records]
        self.assertEqual(len(good), 2)

        # Corrupt the file on disk, then re-run load() explicitly.
        self._write(json.dumps(CLIENT_ROW) + "\n" + "{oops\n")
        corrupt_bytes = self._bytes()
        with self.assertRaises(PersistenceError):
            col.load()

        self.assertEqual(col.records, good, "records changed despite a failed load")
        self.assertEqual(self._bytes(), corrupt_bytes, "failed load wrote to the file")

    def test_unreadable_file_raises_persistence_error_and_preserves_state(self) -> None:
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            self.skipTest("cannot exercise permission errors as root")
        self._write_rows([CLIENT_ROW])
        col = RecordCollection(self.path)
        baseline = [dict(r) for r in col.records]

        os.chmod(self.path, 0)
        self.addCleanup(os.chmod, self.path, stat.S_IRUSR | stat.S_IWUSR)
        try:
            fd = os.open(self.path, os.O_RDONLY)
        except PermissionError:
            pass
        else:  # pragma: no cover - filesystem ignores mode 0 (some CI)
            os.close(fd)
            self.skipTest("filesystem does not enforce mode 0")

        with self.assertRaises(PersistenceError) as ctx:
            col.load()
        self.assertIn(self.path, str(ctx.exception))
        self.assertEqual(col.records, baseline, "records changed on an unreadable file")

    def test_unreadable_file_at_construction_raises_persistence_error(self) -> None:
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            self.skipTest("cannot exercise permission errors as root")
        self._write_rows([CLIENT_ROW])
        os.chmod(self.path, 0)
        self.addCleanup(os.chmod, self.path, stat.S_IRUSR | stat.S_IWUSR)
        try:
            fd = os.open(self.path, os.O_RDONLY)
        except PermissionError:
            pass
        else:  # pragma: no cover
            os.close(fd)
            self.skipTest("filesystem does not enforce mode 0")

        with self.assertRaises(PersistenceError):
            RecordCollection(self.path)

    # ---- load-time structural validation --------------------------------
    def test_valid_stored_rows_including_no_record_type_load(self) -> None:
        client_without_type = {k: v for k, v in CLIENT_ROW.items() if k != "record_type"}
        self._write_rows([client_without_type, AIRLINE_ROW, FLIGHT_ROW])
        col = RecordCollection(self.path)
        self.assertEqual(len(col.records), 3)

    def test_structurally_incomplete_row_raises_with_path_and_line(self) -> None:
        bad_client = {k: v for k, v in CLIENT_ROW.items() if k != "city"}
        self._write_rows([AIRLINE_ROW, bad_client])
        before = self._bytes()
        with self.assertRaises(PersistenceError) as ctx:
            RecordCollection(self.path)
        msg = str(ctx.exception)
        self.assertIn(f"{self.path}:2:", msg)
        self.assertIn("incomplete Client", msg)
        self.assertIn("city", msg)
        self.assertEqual(self._bytes(), before)

    def test_ambiguous_row_raises_with_line(self) -> None:
        ambiguous = {**CLIENT_ROW, "company_name": "Also An Airline"}
        self._write_rows([AIRLINE_ROW, ambiguous])
        before = self._bytes()
        with self.assertRaises(PersistenceError) as ctx:
            RecordCollection(self.path)
        self.assertIn(f"{self.path}:2:", str(ctx.exception))
        self.assertIn("ambiguous", str(ctx.exception))
        self.assertEqual(self._bytes(), before)

    def test_unrecognised_row_raises_with_line(self) -> None:
        self._write_rows([CLIENT_ROW, {"id": 7, "record_type": "client"}])
        before = self._bytes()
        with self.assertRaises(PersistenceError) as ctx:
            RecordCollection(self.path)
        self.assertIn(f"{self.path}:2:", str(ctx.exception))
        self.assertIn("unrecognised", str(ctx.exception))
        self.assertEqual(self._bytes(), before)

    def test_boolean_stored_id_raises_on_load(self) -> None:
        self._write_rows([{**AIRLINE_ROW, "id": True}])
        before = self._bytes()
        with self.assertRaises(PersistenceError) as ctx:
            RecordCollection(self.path)
        self.assertIn(f"{self.path}:1:", str(ctx.exception))
        self.assertIn("boolean", str(ctx.exception))
        self.assertEqual(self._bytes(), before)

    def test_orphaned_flight_still_loads(self) -> None:
        orphan = {
            "client_id": 999999,
            "airline_id": 888888,
            "date": "2026-12-01T09:15:00",
            "start_city": "Nowhere",
            "end_city": "Elsewhere",
        }
        self._write_rows([orphan])
        col = RecordCollection(self.path)
        self.assertEqual(len(col.records), 1)
        self.assertEqual(col.records[0]["client_id"], 999999)
        self.assertIsInstance(col.records[0]["date"], datetime)

    def test_structural_failure_preserves_prior_in_memory_records(self) -> None:
        self._write_rows([CLIENT_ROW, AIRLINE_ROW])
        col = RecordCollection(self.path)
        good = [dict(r) for r in col.records]

        # Corrupt the file with an ambiguous row, then re-run load() explicitly.
        self._write_rows([CLIENT_ROW, {**AIRLINE_ROW, "name": "Wat"}])
        corrupt_bytes = self._bytes()
        with self.assertRaises(PersistenceError):
            col.load()
        self.assertEqual(col.records, good, "records changed despite a failed load")
        self.assertEqual(self._bytes(), corrupt_bytes, "failed load wrote to the file")


class SaveHardening(unittest.TestCase):
    def setUp(self) -> None:
        self._real_data_existed = os.path.exists(REAL_DATA_FILE)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "records.jsonl")

    def tearDown(self) -> None:
        self.assertEqual(
            os.path.exists(REAL_DATA_FILE),
            self._real_data_existed,
            "a test touched the real src/data/records.jsonl",
        )

    # ---- helpers ----------------------------------------------------------
    def _bytes(self) -> bytes:
        with open(self.path, "rb") as fh:
            return fh.read()

    def _temp_files(self) -> list[str]:
        return [n for n in os.listdir(self.tmp.name) if n.endswith(".tmp")]

    def _seed(self, *rows) -> RecordCollection:
        """A collection whose file already holds ``rows`` (saved atomically)."""
        col = RecordCollection(self.path)
        for row in rows:
            col.add(dict(row))
        return col

    # ---- success --------------------------------------------------------
    def test_successful_save_then_reload_round_trip(self) -> None:
        col = RecordCollection(self.path)
        col.add(dict(CLIENT_ROW))
        col.add({**FLIGHT_ROW, "date": datetime(2026, 9, 10, 14, 30)})

        lines = [ln for ln in self._bytes().decode("utf-8").splitlines() if ln]
        self.assertEqual(len(lines), 2)
        for ln in lines:
            self.assertIsInstance(json.loads(ln), dict)
        self.assertEqual(self._temp_files(), [], "temp file left after a good save")

        reloaded = RecordCollection(self.path)
        self.assertEqual(len(reloaded.records), 2)
        client = next(r for r in reloaded.records if r.get("record_type") == "client")
        flight = next(r for r in reloaded.records if "start_city" in r)
        self.assertEqual(client["name"], "Alice Example")
        self.assertEqual(flight["date"], datetime(2026, 9, 10, 14, 30))

    def test_save_does_not_leave_temp_files_behind(self) -> None:
        col = self._seed(CLIENT_ROW, AIRLINE_ROW)
        col.save()
        col.save()
        self.assertEqual(self._temp_files(), [])

    # ---- close-time persistence contract -------------------------------
    def test_close_time_explicit_save_persists_current_state_and_reloads(self) -> None:
        # Calling save() explicitly on a live RecordCollection persists its
        # current state, and a fresh RecordCollection reloads the same state.
        # Save-failure -> PersistenceError, unchanged file and no leftover temp
        # file are covered by test_replace_failure_preserves_file_and_cleans_temp
        # and the other failure tests, which also call save() explicitly.
        col = self._seed(CLIENT_ROW, AIRLINE_ROW)
        col.records.append({**CLIENT_ROW, "id": 2, "name": "Second Client"})

        self.assertIsNone(col.save())  # explicit close-time write, no wrapper
        self.assertEqual(self._temp_files(), [])

        reloaded = RecordCollection(self.path)
        self.assertEqual(reloaded.records, col.records)
        self.assertEqual(
            [r["id"] for r in reloaded.records if r.get("record_type") == "client"],
            [1, 2],
        )

    # ---- serialisation failure ----------------------------------------
    def test_serialisation_failure_preserves_file_and_raises(self) -> None:
        col = self._seed(CLIENT_ROW)
        before = self._bytes()
        col.records.append({"id": 2, "oops": object()})  # not JSON-serialisable

        with self.assertRaises(PersistenceError) as ctx:
            col.save()
        msg = str(ctx.exception)
        self.assertIn(self.path, msg)
        self.assertIn("serialising", msg)
        self.assertEqual(self._bytes(), before, "file changed on a serialisation error")
        self.assertEqual(self._temp_files(), [], "temp file created before serialising")

    # ---- write failure -----------------------------------------------------
    def test_write_failure_preserves_file_and_cleans_temp(self) -> None:
        col = self._seed(CLIENT_ROW)
        before = self._bytes()
        broken = mock_open()
        broken.return_value.write.side_effect = OSError("No space left on device")

        with patch("builtins.open", broken):
            with self.assertRaises(PersistenceError) as ctx:
                col.save()
        msg = str(ctx.exception)
        self.assertIn(self.path, msg)
        self.assertIn("writing the temporary file", msg)
        self.assertEqual(self._bytes(), before, "file changed on a write error")
        self.assertEqual(self._temp_files(), [], "temp file not cleaned up after write error")

    # ---- replace failure ------------------------------------------------
    def test_replace_failure_preserves_file_and_cleans_temp(self) -> None:
        col = self._seed(CLIENT_ROW)
        before = self._bytes()

        with patch("src.record.record_management.os.replace",
                   side_effect=OSError("cross-device link")):
            with self.assertRaises(PersistenceError) as ctx:
                col.save()
        msg = str(ctx.exception)
        self.assertIn(self.path, msg)
        self.assertIn("replacing the destination file", msg)
        self.assertEqual(self._bytes(), before, "file changed on a replace error")
        self.assertEqual(self._temp_files(), [], "temp file not cleaned up after replace error")

    def test_temp_cleanup_failure_does_not_mask_original_error(self) -> None:
        col = self._seed(CLIENT_ROW)
        before = self._bytes()

        with patch("src.record.record_management.os.replace",
                   side_effect=OSError("replace boom")), \
             patch("src.record.record_management.os.remove",
                   side_effect=OSError("remove boom")):
            with self.assertRaises(PersistenceError) as ctx:
                col.save()
        msg = str(ctx.exception)
        self.assertIn("replacing the destination file", msg)
        self.assertNotIn("remove boom", msg)
        self.assertEqual(self._bytes(), before)

    # ---- in-memory rollback on save failure ----------------------------
    def test_add_rolls_back_in_memory_when_save_fails(self) -> None:
        col = self._seed(CLIENT_ROW)
        before_records = [dict(r) for r in col.records]
        before_bytes = self._bytes()

        with patch("src.record.record_management.os.replace",
                   side_effect=OSError("nope")):
            with self.assertRaises(PersistenceError):
                col.add(dict(AIRLINE_ROW))

        self.assertEqual(col.records, before_records, "add() was not rolled back")
        self.assertEqual(self._bytes(), before_bytes)
        self.assertEqual(self._temp_files(), [])

    def test_update_rolls_back_in_memory_when_save_fails(self) -> None:
        col = self._seed(CLIENT_ROW, {**CLIENT_ROW, "id": 2, "name": "Bob"})
        before_records = [dict(r) for r in col.records]
        before_bytes = self._bytes()

        with patch("src.record.record_management.os.replace",
                   side_effect=OSError("nope")):
            with self.assertRaises(PersistenceError):
                col.update({**CLIENT_ROW, "name": "CHANGED"}, id=1)

        self.assertEqual(col.records, before_records, "update() was not rolled back")
        self.assertEqual(self._bytes(), before_bytes)
        self.assertEqual(self._temp_files(), [])

    def test_delete_rolls_back_in_memory_when_save_fails(self) -> None:
        col = self._seed(CLIENT_ROW, {**CLIENT_ROW, "id": 2, "name": "Bob"})
        before_records = [dict(r) for r in col.records]
        before_bytes = self._bytes()

        with patch("src.record.record_management.os.replace",
                   side_effect=OSError("nope")):
            with self.assertRaises(PersistenceError):
                col.delete(id=1)

        self.assertEqual(col.records, before_records, "delete() was not rolled back")
        self.assertEqual(self._bytes(), before_bytes)
        self.assertEqual(self._temp_files(), [])

    # ---- success + return-value contracts ----------------------------
    def test_add_returns_none_and_persists_on_success(self) -> None:
        col = RecordCollection(self.path)
        self.assertIsNone(col.add(dict(CLIENT_ROW)))
        self.assertEqual(RecordCollection(self.path).records[0]["name"], "Alice Example")

    def test_update_and_delete_return_true_on_match(self) -> None:
        col = self._seed(CLIENT_ROW, {**CLIENT_ROW, "id": 2, "name": "Bob"})
        self.assertIs(col.update({**CLIENT_ROW, "name": "Updated"}, id=1), True)
        self.assertIs(col.delete(id=2), True)
        reloaded = RecordCollection(self.path)
        self.assertEqual([r["id"] for r in reloaded.records], [1])
        self.assertEqual(reloaded.records[0]["name"], "Updated")

    def test_no_match_update_or_delete_returns_false_without_saving(self) -> None:
        col = self._seed(CLIENT_ROW)
        before_bytes = self._bytes()
        before_records = [dict(r) for r in col.records]

        with patch.object(RecordCollection, "save",
                          side_effect=AssertionError("save() must not be called")):
            self.assertIs(col.update(dict(CLIENT_ROW), id=999), False)
            self.assertIs(col.delete(id=999), False)

        self.assertEqual(col.records, before_records)
        self.assertEqual(self._bytes(), before_bytes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
