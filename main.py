import json
import sys

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QApplication, QWidget, QFormLayout, QLineEdit, QPushButton, QLabel,
    QDateEdit, QRadioButton, QGroupBox, QVBoxLayout, QButtonGroup, QCheckBox, QMainWindow
)
import ApiService
import DataAnalysis
from KoboldCPPIntegration import KoboldCPP


class Main(QMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        window = QWidget()

        self.setWindowTitle("LLM job analyzer")
        self.setGeometry(100, 100, 400, 600)

        self.layout = QFormLayout()

        self.locationField = QLineEdit()
        self.layout.addRow("location:", self.locationField)

        self.useDate = QPushButton("Use date")
        self.useDate.setCheckable(True)
        self.useDate.clicked.connect(self.check_box)

        self.startDate = QDateEdit(calendarPopup=True)
        self.startDate.setMinimumDate(QDate(2016, 1,1))
        self.startDate.setMaximumDate(QDate.currentDate())

        self.endDate = QDateEdit(calendarPopup=True)
        self.endDate.setMinimumDate(QDate(2016, 1, 1))
        self.endDate.setMaximumDate(QDate.currentDate())
        self.layout.addRow(self.useDate)
        self.layout.addRow("start-date:", self.startDate)
        self.layout.addRow("end-date:", self.endDate)

        graphTypeBox = QGroupBox("Graph types")
        graphTypeLayout = QVBoxLayout()
        self.pieBox = QCheckBox("pie")
        self.stapleBox = QCheckBox("staple")
        self.timeBox = QCheckBox("time")
        graphTypeLayout.addWidget(self.pieBox)
        graphTypeLayout.addWidget(self.stapleBox)
        graphTypeLayout.addWidget(self.timeBox)
        graphTypeBox.setLayout(graphTypeLayout)
        self.layout.addRow(graphTypeBox)

        self.extraApis = QLineEdit()
        self.layout.addRow(QLabel("additional API:s (separate with ','):"))
        self.layout.addRow(self.extraApis)

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
        self.layout.addRow(llmGroupBox)

        self.canvas = DataAnalysis.DataAnalysis()
        self.layout.addRow(self.canvas)

        window.setLayout(self.layout)
        self.setCentralWidget(window)


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
        self.runButton.setEnabled(False)
        apiService = ApiService.ApiService()
        responses = apiService.load()

        try:
            descriptions = []
            dates = []
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

                    date_text = data['hits'][0]['publication_date']
                    if date_text is not None:
                        dates.append(date_text)
                    else:
                        print(data)
                except:
                    print("could not get description")
                    print(response)
                    pass

            # print((descriptions, dates))
            examples = []
            for date in dates: # TODO: byt ut innehållet i 'skills' med data från LLM
                examples.append(json.dumps({"skills":["abc", "cba", "zxc"], "date":date}))
                examples.append(json.dumps({"skills":["abc"], "date":"2025-04-06T11:56:47"}))
                examples.append(json.dumps({"skills": ["cba"], "date": "2025-07-06T11:56:47"}))

            #layout = QVBoxLayout()
            self.canvas.load_data(examples, {"pie":self.pieBox.isChecked(),
                                                "time":self.timeBox.isChecked(),
                                                "staple":self.stapleBox.isChecked()})

            self.canvas.plot_data()
            #layout.addWidget(analysis.plot_data())
            #self.window.setLayout(layout)

            """
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
            """



        except Exception as e:
            print("Connection failed:")

        self.runButton.setEnabled(True)




if __name__ == '__main__':
    app = QApplication([])
    window = Main()
    window.show()
    app.exec()


