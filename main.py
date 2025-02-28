import sys

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import QApplication, QWidget, QLineEdit, QDateEdit, QPushButton, QGridLayout, QLabel, QLayout, \
    QFormLayout
import ApiService

class Main:
    def __init__(self):
        app = QApplication([])
        window = QWidget()

        window.setWindowTitle("LLM job analyzer")
        window.setGeometry(100, 100, 400, 600)

        layout = QFormLayout()

        self.locationField = QLineEdit()
        layout.addRow("location:", self.locationField)

        self.useDate = QPushButton("Use date")
        self.useDate.setCheckable(True)
        self.useDate.clicked.connect(self.check_box)

        self.startDate = QDateEdit(calendarPopup=True)
        self.startDate.setMinimumDate(QDate(2016, 1,1))
        self.startDate.setMaximumDate(QDate.currentDate())

        self.endDate = QDateEdit(calendarPopup=True)
        self.endDate.setMinimumDate(QDate(2016, 1, 1))
        self.endDate.setMaximumDate(QDate.currentDate())
        layout.addRow(self.useDate)
        layout.addRow("start-date:", self.startDate)
        layout.addRow("end-date:", self.endDate)

        self.extraApis = QLineEdit()
        layout.addRow(QLabel("additional API:s (separate with ','):"))
        layout.addRow(self.extraApis)

        self.submitButton = QPushButton("start")
        self.submitButton.clicked.connect(self.test_button)
        layout.addRow(self.submitButton)

        window.setLayout(layout)
        window.show()
        sys.exit(app.exec())

    def test_button(self):
        print ("skickat")
        self.submitButton.setEnabled(False)
        # apiService = ApiService.ApiService()
        # apiService.load()

    def check_box(self):
        if self.useDate.isChecked():
            self.useDate.setCheckable(False)
            self.startDate.setEnabled(True)
            self.endDate.setEnabled(True)
        else:
            self.useDate.setCheckable(True)
            self.startDate.setEnabled(False)
            self.endDate.setEnabled(False)

if __name__ == '__main__':
    Main()


