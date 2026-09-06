from dataclasses import fields
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedLayout,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from record.record_management import (
    RecordCollection,
    RecordManager
)

from record.airline_record import AirlineRecord
from record.client_record import ClientRecord
from record.flight_record import FlightRecord
from record.record_types import RecordType


class RecordGUI(QMainWindow):

    def __init__(self, collector: RecordCollection):
        super().__init__() # initialise QMainWindow

        self.collector = collector # associate RecordCollection to self variable
        # Create a record manager for manipulating each record type
        self.record_manager = RecordManager(self.collector)


        self.setWindowTitle("Record Management System Project")
        #self.resize(750, 600) # window size
        self.resize(1000, 1000)

        ############################################
        ## Main canvas / widget ##
        # create a blank canvas, set QWidget as the main window
        # stack the widgets vertically (input form on top, record table on the bottom etc)
        ############################################
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # Secondary canvas /  form group ---
        form_group = QGroupBox("Add New Record")
        form_group_layout = QVBoxLayout()

        # Drop-Down Menu
        # Set drop-down label names
        self.type_dropdown = QComboBox()
        self.type_dropdown.addItems(
            ["Client Record", "Airline Record", "Flight Record"]
        )
        self.type_dropdown.currentIndexChanged.connect(self.refresh_table)
        


        ## Combine all 3 forms into a single form ##
        self.stacked_layout = QStackedLayout()


        ############################################
        # Form 0: Client Record Fields
        ############################################
        side_by_side_layout = QHBoxLayout()

        self.form_client = QWidget()
        layout_combined_client = QFormLayout(self.form_client)
        layout_left_client = QFormLayout()
        layout_right_client = QFormLayout()

        # Dictionary to store client fields from dataclass
        self.client_fields: dict[str, QLineEdit] = {}

        # Loop through dataclass fields and auto-populate the widgets
        for index, f in enumerate(fields(ClientRecord)):
            label_text = f.metadata.get("label", f.name.replace("_", " ").title())
            placeholder = f.metadata.get("placeholder", "")

            widget = QLineEdit()
            if placeholder:
                widget.setPlaceholderText(placeholder)

            # Store dataclass fields 
            self.client_fields[f.name] = widget

            # First 6 fields (indices 0 to 5) go Left; everything else goes Right
            if index < 6:
                layout_left_client.addRow(f"{label_text}:", widget)
            else:
                layout_right_client.addRow(f"{label_text}:", widget)

        # Combine left and right forms to form a grid
        side_by_side_layout.addLayout(layout_left_client)
        side_by_side_layout.addLayout(layout_right_client)
        layout_combined_client.addRow(side_by_side_layout)


        ############################################
        ## Form 1: Airline Record Fields ##
        ############################################
        self.form_airline = QWidget()
        layout_airline = QFormLayout(self.form_airline)

        # Dictionary to store airline fields from dataclass
        self.airline_fields: dict[str, QLineEdit] = {}

        for index, f in enumerate(fields(AirlineRecord)):
            label_text = f.metadata.get("label", f.name.replace("_", " ").title())
            placeholder = f.metadata.get("placeholder", "")

            widget = QLineEdit()
            if placeholder:
                widget.setPlaceholderText(placeholder)

            # Store dataclass fields 
            self.airline_fields[f.name] = widget

            layout_airline.addRow(f"{label_text}:", widget)


        ############################################
        # Form 2: Flight Record Fields
        ############################################
        self.form_flight = QWidget()
        layout_flight = QFormLayout(self.form_flight)

        # Dictionary to store flight fields from dataclass
        self.flight_fields: dict[str, QLineEdit] = {}

        for index, f in enumerate(fields(FlightRecord)):
            label_text = f.metadata.get("label", f.name.replace("_", " ").title())
            placeholder = f.metadata.get("placeholder", "")

            widget = QLineEdit()
            if placeholder:
                widget.setPlaceholderText(placeholder)

            # Store dataclass fields 
            self.flight_fields[f.name] = widget

            layout_flight.addRow(f"{label_text}:", widget)


        ############################################
        # Combine all 3 Forms together
        ############################################
        self.stacked_layout.addWidget(self.form_client)
        self.stacked_layout.addWidget(self.form_airline)
        self.stacked_layout.addWidget(self.form_flight)

        # Connect the dropdown to the visible form
        self.type_dropdown.currentIndexChanged.connect(
            self.stacked_layout.setCurrentIndex
        )
        ############################################
        ## Assemble the Drop-Down Menu ##
        ############################################
        form_group_layout.addWidget(self.type_dropdown)
        form_group_layout.addLayout(self.stacked_layout)

        self.add_button = QPushButton("Add Record")
        self.add_button.clicked.connect(self.on_add)
        form_group_layout.addWidget(self.add_button)

        form_group.setLayout(form_group_layout)
        main_layout.addWidget(form_group)

        ############################################
        ## Table View ##
        ############################################
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["Client ID", "Name / Details", "Type"]
        )
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )

        main_layout.addWidget(self.table)
        self.refresh_table()


    ############################################
    # Event Handlers [ add, delete, update ]
    ############################################ 
    def on_add(self):
        """Triggered when the user clicks the 'Add Record' button in the GUI."""
        current_form_index = self.type_dropdown.currentIndex()

        handler_map = {
            0: (self.client_fields, self.record_manager, RecordType.CLIENT),
            1: (self.airline_fields, self.record_manager, RecordType.AIRLINE),
            2: (self.flight_fields, self.record_manager, RecordType.FLIGHT)
        }

        active_fields, manager, record_type = handler_map[current_form_index]

        if current_form_index == 0:  # Client Form
            # Fetch all QLineEdit text values into a dictionary
            record_data = {
                field_name: widget.text().strip()
                for field_name, widget in active_fields.items()
            }

            # Pass the dictionary to collector.add()
            try:
                manager.create_record(record_type, record_data)

                # Clear all form input boxes in a single loop
                for widget in self.client_fields.values():
                    widget.clear()

                self.refresh_table()

            except TypeError as e:
                QMessageBox.warning(self, "Invalid Record Data", f"Failed to create record:\n{e}")

        elif current_form_index == 1:  # Airline Form
            record_data = {
                field_name: widget.text().strip()
                for field_name, widget in self.airline_fields.items()
            }

            # Pass dictionary to collector.add()
            self.collector.add(record_data)

            for widget in self.airline_fields.values():
                widget.clear()

        # Refresh the table view to show the new record
        self.refresh_table()

    def refresh_table(self):
        """Refreshes table columns and populates the latest records using collector.find()."""
        # Set active record type based on UI selection (e.g., combobox selection)
        current_index = self.type_dropdown.currentIndex()

        type_map = {
            0: (ClientRecord, RecordType.CLIENT),
            1: (AirlineRecord, RecordType.AIRLINE),
            2: (FlightRecord, RecordType.FLIGHT)
        }

        if current_index not in type_map:
            return

        record_class, record_type = type_map[current_index]

        # Fetch column headers dynamically from the Dataclass fields
        model_fields = fields(record_class)
        self.table.setColumnCount(len(model_fields))

        headers = [
            f.metadata.get("label", f.name.replace("_", " ").title())
            for f in model_fields
        ]
        self.table.setHorizontalHeaderLabels(headers)

        # Poll latest records via collector.find()
        # Safely handle single dict, list of dicts, or None returns
        #raw_records = self.collector.find(record_type=record_type)
        #raw_records = self.collector.find() # fine a single record
        raw_records = self.collector.records

        if raw_records is None:
            records = []
        elif isinstance(raw_records, dict):
            records = [raw_records]
        else:
            records = raw_records

        # Clear existing table rows
        self.table.setRowCount(0)

        target_str = record_type.value.lower() if hasattr(record_type, "value") else str(record_type).lower()

        records = [
            rec for rec in records
            if str(rec.get("record_type", "")).lower() == target_str
        ]

        # Populate rows and cells
        for record in records:
            row_position = self.table.rowCount()
            self.table.insertRow(row_position)

            for col_idx, field in enumerate(model_fields):
                raw_val = record.get(field.name, "")

                # If the value inside the dict is an Enum, extract its string value
                val_str = raw_val.value if hasattr(raw_val, "value") else str(raw_val)

                # QTableWidgetItem MUST be instantiated with a string
                item = QTableWidgetItem(val_str)
                # Pass row_position (int) and col_idx (int)
                self.table.setItem(row_position, col_idx, item)
