import json
import sys

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QApplication, QWidget, QFormLayout, QLineEdit, QPushButton, QLabel,
    QDateEdit, QRadioButton, QGroupBox, QVBoxLayout, QButtonGroup, QCheckBox
)
import ApiService
from KoboldCPPIntegration import KoboldCPP


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

        graphTypeBox = QGroupBox("Graph types")
        graphTypeLayout = QVBoxLayout()
        self.pieBox = QCheckBox("pie")
        self.stapleBox = QCheckBox("staple")
        self.timeBox = QCheckBox("time")
        graphTypeLayout.addWidget(self.pieBox)
        graphTypeLayout.addWidget(self.stapleBox)
        graphTypeLayout.addWidget(self.timeBox)
        graphTypeBox.setLayout(graphTypeLayout)
        layout.addRow(graphTypeBox)

        self.extraApis = QLineEdit()
        layout.addRow(QLabel("additional API:s (separate with ','):"))
        layout.addRow(self.extraApis)

        # LLM setup fields
        llmGroupBox = QGroupBox("LLM Connection:")
        llmLayout = QVBoxLayout()

        self.koboldRadio = QRadioButton("koboldCPP")
        self.deepseekRadio = QRadioButton("deepseek")
        self.openAIRadio = QRadioButton("openAI")
        self.deepseekRadio.setChecked(True)

        # Disabled for now
        self.koboldRadio.setDisabled(True)
        self.openAIRadio.setDisabled(True)

        self.llmButtonGroup = QButtonGroup()
        self.llmButtonGroup.addButton(self.koboldRadio)
        self.llmButtonGroup.addButton(self.deepseekRadio)
        self.llmButtonGroup.addButton(self.openAIRadio)
        llmLayout.addWidget(self.koboldRadio)
        llmLayout.addWidget(self.deepseekRadio)
        llmLayout.addWidget(self.openAIRadio)

        self.koboldURLField = QLineEdit()
        self.koboldURLField.setPlaceholderText("Enter koboldCPP URL")
        self.koboldURLField.setText("http://localhost:5001")

        llmLayout.addWidget(self.koboldURLField)

        self.testConnectionButton = QPushButton("Test Connection")
        #self.testConnectionButton.clicked.connect(self.connect_llm)
        llmLayout.addWidget(self.testConnectionButton)

        self.runButton = QPushButton("Run")
        self.runButton.clicked.connect(self.run_program)
        llmLayout.addWidget(self.runButton)

        llmGroupBox.setLayout(llmLayout)
        layout.addRow(llmGroupBox)

        window.setLayout(layout)
        window.show()
        sys.exit(app.exec())

    def check_box(self):
        if self.useDate.isChecked():
            self.useDate.setCheckable(False)
            self.startDate.setEnabled(True)
            self.endDate.setEnabled(True)
        else:
            self.useDate.setCheckable(True)
            self.startDate.setEnabled(False)
            self.endDate.setEnabled(False)

    def connect_llm(self):
        try:
            if self.koboldRadio.isChecked():
                url = self.koboldURLField.text()
                if not url:
                    return
                print(f"Testing koboldCPP connection with URL: {url}")
                kobold = KoboldCPP(url+"/api/v1")
                connected = kobold.check_connection()
                #print(f"Connected: {connected}")
                if not connected.index(0):
                    print("Connection failed")
                    return
                else:
                    print("Connection successful| Version: "+connected.index(1))
        except:
            print("Connection failed")





        """
        elif self.deepseekRadio.isChecked():
            api_key = self.deepseekAPIKeyField.text()
            print(f"Testing deepseek connection with API key: {api_key}")
        elif self.openAIRadio.isChecked():
            api_key = self.openAIApiKeyField.text()
            print(f"Testing openAI connection with API key: {api_key}")
        """

    def run_program(self):

        apiService = ApiService.ApiService()
        responses = apiService.load()

        try:
            descriptions = []
            for response in responses:
                try:
                    data = json.loads(response.decode('utf-8'))
                    description_text = data['hits'][0]['description']['text']
                    if description_text is not None:
                        #print(description_text)
                        descriptions.append(description_text)
                    else:
                        print("no description for:")
                        print(data)
                except:
                    print("could not get description")
                    print(response)
                    pass

            #print(descriptions)
            if self.koboldRadio.isChecked():
                url = self.koboldURLField.text()
                if not url:
                    return
                print(f"Running using koboldCPP connection with URL: {url}")
                kobold = KoboldCPP(url+"/api/v1")
                kobold.send_description(descriptions)
            if self.deepseekRadio.isChecked():
                kobold = KoboldCPP()
                kobold.deepseek_send_description(descriptions)



        except Exception as e:
            print("Connection failed:")









if __name__ == '__main__':
    Main()


