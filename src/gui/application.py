from dataclasses import fields

from PyQt6.QtCore import QDateTime, Qt
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
        ''' Initialise the main canvas'''
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
        form_group = QGroupBox("")
        form_group_layout = QVBoxLayout()

        ### Clear fields button
        top_left_layout = QHBoxLayout()
        top_left_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        top_left_layout.setContentsMargins(0, 0, 0, 0)
        self.clear_button = QPushButton("Clear Fields")
        self.clear_button.setFixedWidth(85)
        self.clear_button.setFixedHeight(32)
        self.clear_button.clicked.connect(self.clear_fields)
        top_left_layout.addWidget(self.clear_button)
        top_left_layout.addStretch()
        form_group_layout.addLayout(top_left_layout)
        form_group.setLayout(form_group_layout)

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

        self.search_button = QPushButton("Search (leave empty for all)")
        self.add_button = QPushButton("Add Record")
        self.update_button = QPushButton("Update Selected")
        self.delete_button = QPushButton("Delete Selected")

        # Connect EACH button to its respective handler
        self.search_button.clicked.connect(self.on_search)
        self.add_button.clicked.connect(self.on_add)
        self.update_button.clicked.connect(self.on_update)
        self.delete_button.clicked.connect(self.on_delete)

        form_group_layout.addWidget(self.search_button)
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
        #self.refresh_table()


    ############################################
    # Event Handlers [ add, delete, update ]
    ############################################ 

    def clear_fields(self):
            """Resets input widgets for the currently active form, preserving record_type."""
            current_form_index = self.type_dropdown.currentIndex()
            handler_map = {
                0: self.client_fields,
                1: self.airline_fields,
                2: self.flight_fields,
            }
            active_fields = handler_map.get(current_form_index, {})

            for field_name, widget in active_fields.items():
                # Skip clearing the record_type field or the dropdown widget itself
                if field_name == "record_type" or widget == self.type_dropdown:
                    continue

                if isinstance(widget, QLineEdit):
                    widget.clear()
                elif isinstance(widget, QDateTimeEdit):
                    widget.setDateTime(QDateTime.currentDateTime())
                elif isinstance(widget, QComboBox):
                    widget.setCurrentIndex(0)

    def refresh_table(self, records=None):
        """Refreshes table columns and populates the latest records using collector.find() & collector.search()."""
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

        # Determine source data (collector vs passed search records)
        is_search_mode = records is not None
        raw_source = records if is_search_mode else self.collector.records

        # Safely handle single dict, list of dicts, or None returns
        if raw_source is None:
            raw_list = []
        elif isinstance(raw_source, dict):
            raw_list = [raw_source]
        elif isinstance(raw_source, list):
            raw_list = raw_source
        else:
            raw_list = [raw_source]

        # Filter by record type ONLY during standard tab switches
        target_records = []
        if not is_search_mode:
            target_str = record_type.value.lower() if hasattr(record_type, "value") else str(record_type).lower()
            
            for rec in raw_list:
                rec_dict = rec if isinstance(rec, dict) else getattr(rec, "__dict__", {})
                rec_type = str(rec_dict.get("record_type", "")).strip().lower()

                # Flight records lack a record_type key or have it empty/none
                if target_str == "":
                    if not rec_type or rec_type == "none":
                        target_records.append(rec_dict)
                else:
                    if rec_type == target_str:
                        target_records.append(rec_dict)
        else:
            target_records = [
                rec if isinstance(rec, dict) else getattr(rec, "__dict__", {})
                for rec in raw_list
            ]


        # Clear existing table rows
        self.table.blockSignals(True)
        self.table.setRowCount(0)

        # Populate rows and cells
        for record in target_records:
            if not record:
                continue

            row_position = self.table.rowCount()
            self.table.insertRow(row_position)

            for col_idx, field in enumerate(model_fields):
                raw_val = record.get(field.name, "")

                if raw_val == "" and field.name == "id":
                    raw_val = record.get("record_id", record.get("client_id", record.get("airline_id", "")))

                # If the value inside the dict is an Enum, extract its string value
                val_str = raw_val.value if hasattr(raw_val, "value") else str(raw_val)

                # QTableWidgetItem MUST be instantiated with a string
                item = QTableWidgetItem(val_str)

                # Attach the untouched original record dictionary to Column 0
                if col_idx == 0:
                    item.setData(Qt.ItemDataRole.UserRole, record)

                # Pass row_position (int) and col_idx (int)
                self.table.setItem(row_position, col_idx, item)

        self.table.blockSignals(False)

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
            self.clear_fields()

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
            record_id_str = id_item.text().strip() if id_item else ""

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

                # Handle FLIGHT with composite criteria
                if record_type == RecordType.FLIGHT:
                        # Retrieve original raw record dict attached to column 0
                        original_data = id_item.data(Qt.ItemDataRole.UserRole)

                        success = self.record_manager.delete_record(
                        record_type=record_type,
                        row_index=selected_row,
                        client_id=original_data.get("client_id"),
                        airline_id=original_data.get("airline_id"),
                        date=original_data.get("date"),
                        start_city=original_data.get("start_city"),
                        end_city=original_data.get("end_city")
                        )

                success = self.record_manager.delete_record(
                    record_type=record_type,
                    record_id=record_id,
                    row_index=selected_row 
                )

                if success:
                    self.refresh_table()
                    self.clear_fields()
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

                # Handle FLIGHT with composite criteria
                if record_type == RecordType.FLIGHT:
                        # Retrieve original raw record dict attached to column 0
                        original_data = id_item.data(Qt.ItemDataRole.UserRole)

                        success = self.record_manager.update_record(
                            record_type=record_type,
                            data=record_data,
                            row_index=selected_row,
                            client_id=original_data.get("client_id"),
                            airline_id=original_data.get("airline_id"),
                            date=original_data.get("date"),
                            start_city=original_data.get("start_city"),
                            end_city=original_data.get("end_city")
                        )
                else:
                    # Update directly through RecordManager
                    success = self.record_manager.update_record(
                        record_type=record_type,
                        data=record_data,
                        record_id=record_id,
                        row_index=selected_row
                    )

                if success:
                    self.refresh_table()
                    self.clear_fields()
                else:
                    QMessageBox.warning(self, "Update Failed", "Record could not be updated.")

            except Exception as e:
                QMessageBox.warning(self, "Update Error", f"Failed to update record:\n{e}")

    def on_search(self):
        """Triggered when the user clicks 'Search'. Searches active fields."""
        current_index = self.type_dropdown.currentIndex()

        handler_map = {
            0: (self.client_fields, RecordType.CLIENT),
            1: (self.airline_fields, RecordType.AIRLINE),
            2: (self.flight_fields, RecordType.FLIGHT),
        }

        if current_index not in handler_map:
            print("[DEBUG Search] Invalid tab index selected:", current_index)
            return

        active_fields, record_type = handler_map[current_index]

        # Extract raw data from fields
        extracted_data = self._extract_data(active_fields)

        # Filter out empty criteria
        search_criteria = {
            key: val for key, val in extracted_data.items() 
            if val != "" and val is not None
        }

        # --- DEBUG CHECK AROUND EMPTY CRITERIA ---
        if not search_criteria:
            self.refresh_table()
            return

        try:

            filtered_records = self.record_manager.search_display_record(
                record_type=record_type,
                **search_criteria
            )
            
            # Display search results in table
            self.refresh_table(filtered_records)

        except Exception as e:
            QMessageBox.warning(self, "Search Error", f"Failed to execute search:\n{e}")

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