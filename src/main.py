import sys
from PyQt6.QtWidgets import QApplication

# Import your core architecture modules
from record.record_management import RecordCollection
from gui.application import RecordGUI


def main():
    # Initialize the PyQt Application
    app = QApplication(sys.argv)

    # Instantiate the Collector
    collection = RecordCollection()

    # Instantiate the GUI
    window = RecordGUI(collection)
    window.show()

    # Start the PyQt6 Event Loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()