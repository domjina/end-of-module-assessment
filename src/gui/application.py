from dataclasses import fields
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
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

from conf.record_collector import (
    RecordCollection,
    ClientManagement,
    AirlineManagement,
    FlightManagement
)

from record.airline_record import AirlineRecord
from record.client_record import ClientRecord
from record.flight_record import FlightRecord


class RecordGUI(QMainWindow):

    def __init__(self, collector: RecordCollection):
        super().__init__() # initialise QMainWindow

        self.collector = collector # associate RecordCollection to self variable
        # Create dedicated managers for each record type
        self.client_manager = ClientManagement(self.collector)
        self.airline_manager = AirlineManagement(self.collector)
        self.flight_manager = FlightManagement(self.collector)


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
            ["Client Record", "Aireline Record", "Flight Record"]
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
