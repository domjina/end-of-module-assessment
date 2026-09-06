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