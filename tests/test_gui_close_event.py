"""Focused regression tests for RecordGUI.closeEvent (save-on-close).

Covers only the new lifecycle hook added to ``src/gui/application.py``:
successful save accepts the close, a ``PersistenceError`` surfaces a dialog
and rejects the close. No other GUI behaviour is exercised here.

Headless (``QT_QPA_PLATFORM=offscreen``), no event loop is started, and the
collector always points at a ``tempfile`` path -- the real
``src/data/records.jsonl`` is never created or touched.

Run from the repository root::

    QT_QPA_PLATFORM=offscreen python -m unittest tests.test_gui_close_event -v
"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication

from src.gui.application import RecordGUI
from src.record.record_management import PersistenceError, RecordCollection

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL_DATA_FILE = os.path.join(REPO_ROOT, "src", "data", "records.jsonl")


class CloseEventSaveOnClose(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self._real_data_existed = os.path.exists(REAL_DATA_FILE)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "records.jsonl")
        self.collector = RecordCollection(self.path)
        self.window = RecordGUI(self.collector)
        self.addCleanup(self.window.deleteLater)

    def tearDown(self) -> None:
        self.assertEqual(
            os.path.exists(REAL_DATA_FILE),
            self._real_data_existed,
            "a test touched the real src/data/records.jsonl",
        )

    def test_successful_save_accepts_close(self) -> None:
        self.collector.save = MagicMock(wraps=self.collector.save)
        event = MagicMock()

        self.window.closeEvent(event)

        self.collector.save.assert_called_once()
        event.accept.assert_called_once()
        event.ignore.assert_not_called()

    def test_persistence_error_shows_dialog_and_rejects_close(self) -> None:
        self.collector.save = MagicMock(side_effect=PersistenceError("disk full"))
        event = MagicMock()

        with patch("src.gui.application.QMessageBox.warning") as warning:
            self.window.closeEvent(event)

        self.collector.save.assert_called_once()
        warning.assert_called_once()
        event.ignore.assert_called_once()
        event.accept.assert_not_called()


if __name__ == "__main__":
    unittest.main()
