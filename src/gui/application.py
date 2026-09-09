from dataclasses import fields
from datetime import datetime

from PyQt6.QtCore import QDateTime
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QComboBox,
    QDateTimeEdit,
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

        # Fields to omit from the UI entirely
        EXCLUDE_FIELDS = {"id"}

        # Fields to display as non-editable
        READ_ONLY_FIELDS = {"record_type"}


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

        visible_count = 0

        # Loop through dataclass fields and auto-populate the widgets
        for f in fields(ClientRecord):
            # Skip hidden fields (e.g., 'id')
            if f.name in EXCLUDE_FIELDS:
                continue

            label_text = f.metadata.get("label", f.name.replace("_", " ").title())
            placeholder = f.metadata.get("placeholder", "")

            widget = QLineEdit()
            if placeholder:
                widget.setPlaceholderText(placeholder)

            # Read-only fields (e.g., 'record_type')
            if f.name in READ_ONLY_FIELDS:
                widget.setReadOnly(True)

            # Prefill record_type default value
            if f.name == "record_type":
                # Handles both StrEnum/Enum or standard strings
                default_val = getattr(RecordType.CLIENT, "value", RecordType.CLIENT)
                widget.setText(str(default_val))

            # Store dataclass fields 
            self.client_fields[f.name] = widget

            # First 6 fields (indices 0 to 5) go Left; everything else goes Right
            if visible_count < 6:
                layout_left_client.addRow(f"{label_text}:", widget)
            else:
                layout_right_client.addRow(f"{label_text}:", widget)

            visible_count += 1

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

        # Loop through dataclass fields and auto-populate the widgets
        for f in fields(AirlineRecord):
            # Skip hidden fields (e.g., 'id')
            if f.name in EXCLUDE_FIELDS:
                continue

            label_text = f.metadata.get("label", f.name.replace("_", " ").title())
            placeholder = f.metadata.get("placeholder", "")

            widget = QLineEdit()
            if placeholder:
                widget.setPlaceholderText(placeholder)

            # Read-only fields (e.g., 'record_type')
            if f.name in READ_ONLY_FIELDS:
                widget.setReadOnly(True)

            # Prefill record_type default value
            if f.name == "record_type":
                # Handles both StrEnum/Enum or standard strings
                default_val = getattr(RecordType.AIRLINE, "value", RecordType.AIRLINE)
                widget.setText(str(default_val))

            # Store dataclass fields 
            self.airline_fields[f.name] = widget

            layout_airline.addRow(f"{label_text}:", widget)


        ############################################
        # Form 2: Flight Record Fields
        ############################################
        self.form_flight = QWidget()
        layout_flight = QFormLayout(self.form_flight)

        # Dictionary to store flight fields from dataclass
        self.flight_fields: dict[str, QWidget] = {}

        # Iterate over fields
        for f in fields(FlightRecord):
            if f.name in EXCLUDE_FIELDS:
                continue

            label_text = f.metadata.get("label", f.name.replace("_", " ").title())
            placeholder = f.metadata.get("placeholder", "")

            # Initiate QDateEdit (for date field) OR QLineEdit 
            if f.name == "date":
                widget = QDateTimeEdit()
                widget.setCalendarPopup(True)          # Enables visual dropdown calendar
                widget.setDateTime(QDateTime.currentDateTime())    # Default to current date
                widget.setDisplayFormat("yyyy-MM-dd")  # Enforces YYYY-MM-DD format
            else:
                widget = QLineEdit()
                if placeholder:
                    widget.setPlaceholderText(placeholder)

                if f.name in READ_ONLY_FIELDS:
                    widget.setReadOnly(True)

                if f.name == "record_type":
                    widget.setText("")

            # Store dataclass fields
            self.flight_fields[f.name] = widget

            # Add row to layout
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
        self.update_button = QPushButton("Update Selected")
        self.delete_button = QPushButton("Delete Selected")

        # Connect EACH button to its respective handler
        self.add_button.clicked.connect(self.on_add)
        self.update_button.clicked.connect(self.on_update)
        self.delete_button.clicked.connect(self.on_delete)

        form_group_layout.addWidget(self.add_button)
        form_group_layout.addWidget(self.update_button)
        form_group_layout.addWidget(self.delete_button)

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
        self.table.cellClicked.connect(self.on_table_row_clicked)
        self.refresh_table()


    ############################################
    # Event Handlers [ add, delete, update ]
    ############################################ 
    def refresh_table(self):
        """Refreshes table columns and populates the latest records using collector.find()."""
        # Set active record type based on UI selection (e.g., combobox selection)
        current_index = self.type_dropdown.currentIndex()

        type_map = {
            0: (ClientRecord, RecordType.CLIENT),
            1: (AirlineRecord, RecordType.AIRLINE),
            2: (FlightRecord, "")
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

    def on_add(self):
        """Triggered when the user clicks the 'Add Record' button in the GUI."""
        current_form_index = self.type_dropdown.currentIndex()

        handler_map = {
            0: (self.client_fields, RecordType.CLIENT),
            1: (self.airline_fields, RecordType.AIRLINE),
            2: (self.flight_fields, RecordType.FLIGHT)
        }

        if current_form_index not in handler_map:
            return

        active_fields, record_type = handler_map[current_form_index]
        record_data = self._extract_data(active_fields)

        try:
            # Create record using manager call directly
            self.record_manager.create_record(record_type, record_data)

            # Reset active widgets
            for field_name, widget in active_fields.items():
                if field_name in ("record_type", "id"):
                    continue

                if isinstance(widget, QDateTimeEdit):
                    widget.setDateTime(QDateTime.currentDateTime())
                elif hasattr(widget, "clear"):
                    widget.clear()

            # Ensure default record_type persist
            if "record_type" in active_fields:
                default_val = getattr(record_type, "value", record_type) if record_type else ""
                active_fields["record_type"].setText(str(default_val))

            self.refresh_table()

        except Exception as e:
            QMessageBox.warning(self, "Invalid Record Data", f"Failed to create record:\n{e}")

    def on_delete(self):
            """Triggered when the user clicks 'Delete Record'."""
            selected_row = self.table.currentRow()
            if selected_row < 0:
                QMessageBox.warning(self, "Selection Error", "Please select a row from the table to delete.")
                return

            current_form_index = self.type_dropdown.currentIndex()
            handler_map = {
                0: RecordType.CLIENT,
                1: RecordType.AIRLINE,
                2: RecordType.FLIGHT,
            }
            record_type = handler_map.get(current_form_index)

            # Retrieve record identifier from column 0 (usually "id")
            id_item = self.table.item(selected_row, 0)
            record_id_str = id_item.text() if id_item else ""

            # Confirm before deletion (pop-up box)
            confirm = QMessageBox.question(
                self,
                "Confirm Delete",
                f"Are you sure you want to delete row {selected_row + 1}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

            try:
                # Parse record_id as integer if present
                record_id = int(record_id_str) if record_id_str.isdigit() else record_id_str

                success = self.record_manager.delete_record(
                    record_type=record_type,
                    record_id=record_id,
                    row_index=selected_row 
                )

                if success:
                    self.refresh_table()
                else:
                    QMessageBox.warning(self, "Delete Failed", "Record could not be found or deleted.")

            except Exception as e:
                QMessageBox.warning(self, "Delete Error", f"Error during deletion:\n{e}")

    def on_update(self):
            """Triggered when the user clicks 'Update Selected'."""
            selected_row = self.table.currentRow()
            if selected_row < 0:
                QMessageBox.warning(self, "Selection Error", "Please select a row from the table to update.")
                return

            current_form_index = self.type_dropdown.currentIndex()
            handler_map = {
                0: (self.client_fields, RecordType.CLIENT),
                1: (self.airline_fields, RecordType.AIRLINE),
                2: (self.flight_fields, RecordType.FLIGHT),
            }
            active_fields, record_type = handler_map[current_form_index]
            record_data = self._extract_data(active_fields)

            # Pull primary key ID from column 0 (if present)
            id_item = self.table.item(selected_row, 0)
            record_id_str = id_item.text() if id_item else ""

            try:
                record_id = int(record_id_str) if record_id_str.isdigit() else record_id_str

                # Update directly through RecordManager
                success = self.record_manager.update_record(
                    record_type=record_type,
                    data=record_data,
                    record_id=record_id,
                    row_index=selected_row
                )

                if success:
                    self.refresh_table()
                else:
                    QMessageBox.warning(self, "Update Failed", "Record could not be updated.")

            except Exception as e:
                QMessageBox.warning(self, "Update Error", f"Failed to update record:\n{e}")

    def on_table_row_clicked(self, row: int, column: int):
            """Populates form fields when a row in the QTableWidget is clicked."""
            current_index = self.type_dropdown.currentIndex()
            handler_map = {
                0: (self.client_fields, ClientRecord),
                1: (self.airline_fields, AirlineRecord),
                2: (self.flight_fields, FlightRecord),
            }

            if current_index not in handler_map:
                return

            active_fields, record_class = handler_map[current_index]
            model_fields = [f.name for f in fields(record_class)]

            for col_idx, field_name in enumerate(model_fields):
                if field_name not in active_fields:
                    continue

                widget = active_fields[field_name]
                item = self.table.item(row, col_idx)
                cell_value = item.text() if item else ""

                if isinstance(widget, QDateTimeEdit):
                    # Parse string date (e.g. "2026-09-08") into QDateTime
                    qdate = QDateTime.fromString(cell_value, "yyyy-MM-dd HH:mm:ss")
                    if qdate.isValid():
                        widget.setDateTime(qdate)
                elif isinstance(widget, QLineEdit):
                    widget.setText(cell_value)

    def _extract_data(self, active_fields: dict) -> dict:
            record_data = {}
            for field_name, widget in active_fields.items():
                if field_name == "record_type":
                    continue

                if isinstance(widget, QDateTimeEdit):
                    record_data[field_name] = widget.dateTime().toString("yyyy-MM-dd HH:mm:ss")
                elif isinstance(widget, QLineEdit):
                    val = widget.text().strip()
                    if val.isdigit() and "id" in field_name:
                        record_data[field_name] = int(val)
                    else:
                        record_data[field_name] = val

            return record_data