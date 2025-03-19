import json
import sys

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QApplication, QWidget, QFormLayout, QLineEdit, QPushButton, QScrollArea,
    QDateEdit, QRadioButton, QGroupBox, QVBoxLayout, QButtonGroup, QCheckBox, QMainWindow
)
import ApiService
import DataAnalysis
from KoboldCPPIntegration import KoboldCPP


class Main(QMainWindow):
    """ Main class for the program, which extends the QMainWindow
    class to create a GUI containing the form and graphs.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        window = QWidget()

        self.setWindowTitle("LLM job analyzer")
        self.setGeometry(100, 100, 800, 600)

        self.layout = QFormLayout()

        self.locationField = QLineEdit()
        self.layout.addRow("location:", self.locationField)

        self.useDate = QCheckBox("Use date")
        self.useDate.setChecked(True)
        self.useDate.clicked.connect(self.check_box)
        self.startDate = QDateEdit(calendarPopup=True)
        self.startDate.setMinimumDate(QDate(2016, 1,1))
        self.startDate.setMaximumDate(QDate.currentDate())
        self.startDate.setDate(QDate.currentDate().addMonths(-1))

        self.endDate = QDateEdit(calendarPopup=True)
        self.endDate.setMinimumDate(QDate(2016, 1, 2))
        self.endDate.setMaximumDate(QDate.currentDate())
        self.endDate.setDate(QDate.currentDate())

        self.layout.addRow(self.useDate)
        self.layout.addRow("start-date:", self.startDate)
        self.layout.addRow("end-date:", self.endDate)

        graphTypeBox = QGroupBox("Graph types")
        graphTypeLayout = QVBoxLayout()
        self.pieBox = QCheckBox("pie")
        self.stapleBox = QCheckBox("bar")
        self.timeBox = QCheckBox("time")

        self.pieBox.setChecked(True)
        self.stapleBox.setChecked(True)
        self.timeBox.setChecked(True)

        graphTypeLayout.addWidget(self.timeBox)
        graphTypeLayout.addWidget(self.stapleBox)
        graphTypeLayout.addWidget(self.pieBox)
        graphTypeBox.setLayout(graphTypeLayout)
        self.layout.addRow(graphTypeBox)

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
        self.canvas.fig.clf()
        #self.canvas.minimumSizeHint()
        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        self.layout.addRow(scroll)

        window.setLayout(self.layout)
        self.setCentralWidget(window)

    def resizeEvent(self,event):
        """
        Window event handler called when the window is resized.
        Is used to resize the canvas that the graphs are printed
        in.
        :param event: reSizeEvent
        """
        self.canvas.resize(event.size())

    def check_box(self):
        """ Method for enabling or disabling the
        start and end date fields when clicking the
        use date button.

        """
        if self.useDate.isChecked():
            #self.useDate.setCheckable(False)
            self.startDate.setEnabled(True)
            self.endDate.setEnabled(True)
        else:
            #self.useDate.setCheckable(True)
            self.startDate.setEnabled(False)
            self.endDate.setEnabled(False)

    def connect_llm(self):
        """ Method for testing the connection to KoboldCPP
        """
        try:
            if self.koboldRadio.isChecked():
                url = self.koboldURLField.text()
                if not url:
                    return
                print(f"Testing koboldCPP connection with URL: {url}")
                kobold = KoboldCPP(url+"/api/v1")
                connected = kobold.check_connection()
                if connected[0] is False:
                    print("Connection failed")
                    return
                else:
                    print("Connection successful| Version: " + str(connected[1]))
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
        """ method for getting and retrieving job postings from APIService,
        which is then passed to the LLM module that identifies skills. Lastly
        the data is sent to the DataAnalysis module which creates graphs.
        """
        self.runButton.setEnabled(False)
        apiService = ApiService.ApiService(self.locationField.text(), self.startDate.date(), self.endDate.date(), self.useDate.isChecked())
        responses = apiService.load()

        try:
            descriptions = []
            dates = []
            ids = []
            for response in responses:
                try:
                    data = json.loads(response.decode('utf-8'))
                    # JSearch
                    if "data" in data:
                        for hit in data["data"]:
                            description_text = hit['job_description']
                            if description_text is not None:
                                # print(description_text)
                                descriptions.append(description_text)
                            else:
                                print("no description for:")
                                print(data)

                            date_text = hit['job_posted_at_datetime_utc']
                            if date_text is not None:
                                dates.append(date_text)
                            else:
                                print(data)

                            job_id = hit['job_id']
                            if job_id is not None and job_id not in ids:
                                ids.append(job_id)
                            else:
                                print(data)
                    # platsbanken, job posting
                    elif "hits" in data:
                        for hit in data['hits']:
                            # job posting
                            if hit['id'] in ids:
                                continue
                            if "description_html" in hit:
                                description_text = hit['description_html']
                                if description_text is not None:
                                    # print(description_text)
                                    descriptions.append(description_text)
                                else:
                                    print("no description for:")
                                    print(data)

                                date_text = hit['date_posted']
                                if date_text is not None:
                                    dates.append(date_text)
                                else:
                                    print(data)

                                job_id = hit['id']
                                if job_id is not None and job_id not in ids:
                                    ids.append(job_id)
                                else:
                                    print(data)
                            # platsbanken
                            else:
                                description_text = hit['description']['text']
                                if description_text is not None:
                                    #print(description_text)
                                    descriptions.append(description_text)
                                else:
                                    print("no description for:")
                                    print(data)

                                date_text = hit['publication_date']
                                if date_text is not None:
                                    dates.append(date_text)
                                else:
                                    print(data)

                                job_id = hit['id']
                                if job_id is not None and job_id not in ids:
                                    ids.append(job_id)
                                else:
                                    print(data)
                except:
                    print("could not get description")
                    print(response)
                    pass

            #print(descriptions)
           # test array
            llm_responses = ["""
            ```json
                {
          "keywords": [
                {"keyword": "development", "LLMRelated": "no"}
              ]
            }
            ```
            """,
            """
            ```json
            {
                "keywords": [
                    {"keyword": "development", "LLMRelated": "no"}
                ]
            }
            ```
            """,
            """
            ```json
            {
                "keywords": [
                    {"keyword": "development", "LLMRelated": "no"}
                ]
            }
           ```
           """
            ]

            #test_dates = [QDate.currentDate(), QDate.currentDate().addMonths(-12), QDate.currentDate().addMonths(14)]

            llm_responses = []
            if self.koboldRadio.isChecked():
                url = self.koboldURLField.text()
                if not url:
                    return
                print(f"Running using koboldCPP connection with URL: {url}")
                kobold = KoboldCPP(url+"/api/v1")
                kobold.send_description(descriptions)
            if self.deepseekRadio.isChecked():
                kobold = KoboldCPP()
                llm_responses = kobold.deepseek_send_description(descriptions)

            index = "json"

            data = []
            i = 0
            for llm_response in llm_responses:
                llm_response = llm_response[llm_response.find(index) + len(index) + 1:]
                llm_response = llm_response[0:llm_response.rfind("```")]
                json_data = json.loads(llm_response)

                #json_data['keywords'].append({"keyword": "sample", "LLMRelated": "yes"})
                print(json_data)

                data.append(json.dumps({"skills":json_data['keywords'], "date": dates[i]}))
                i +=1

            self.canvas.load_data(data, {"pie": self.pieBox.isChecked(),
                                             "time": self.timeBox.isChecked(),
                                             "bar": self.stapleBox.isChecked()})

            self.canvas.plot_data()

        except Exception as e:
            print(e)

        self.runButton.setEnabled(True)




if __name__ == '__main__':
    app = QApplication([])
    window = Main()
    window.show()
    app.exec()