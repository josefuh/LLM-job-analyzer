import matplotlib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
import json

matplotlib.use('QtAgg')

class DataAnalysis(FigureCanvasQTAgg):
    """ Class used to produce graphs to visualize the results
    
    Parameters
    ----------
    results: [str]
        Results produced by the LLM
    graphtype: str, optional
        The graph type assigned by the user, by default None

    Attributes
    ----------
    results: [str]
        Results produced by the LLM
    graphtype: dict
        The graph types assigned by the user

    """

    def __init__(self, results=None, graphtype=None):
        if results is None:
            results = [""]
        if graphtype is None:
            graphtype = {""}

        self.fig, (self.pie, self.bar, self.time) = plt.subplots(3, 1,sharey=False, sharex=False)

        super().__init__(self.fig)

        self.graphtype = graphtype
        self.results = results

    def load_data(self, results, graphtype):
        self.graphtype = graphtype
        self.results = results

    def plot_data(self):
        """ Function used to create and return the graphs to the GUI

        :return: created graphs
        """

        plt.clf()
        y = np.array([35, 25])
        """
        plt.subplot(3, 1, 1)
        self.time = plt.plot(1, 1, y)
        plt.subplot(3, 1, 2)
        self.bar = plt.bar(y,height=50)
        plt.subplot(3, 1, 3)
        self.pie = plt.pie(y, labels=self.results)
        """

        skills = []
        dates = []
        for json_data in self.results:
            raw =json.loads(''.join(json_data))
            for skill in raw['skills']:
                skills.append(skill)
                dates.append(raw['date'])

        data = {"skills":skills, "date":dates}
        print(data)
        if not self.graphtype["pie"] and not self.graphtype["time"] and not self.graphtype["staple"]:
            return

        if self.graphtype["pie"]:
            print("pie")
            pass

        if self.graphtype["time"]:
            plt.subplot(3, 1, 1)

            dataframe = pd.DataFrame(data)
            dataframe['date'] = pd.to_datetime(dataframe['date'])

            dataframe.reset_index()
            occurrences = {}
            for skill in set(skills):
                occurrences[skill] = []


            for index,row in dataframe.iterrows():
                occurrences[row['skills']].append(row['date'])

            for entry in occurrences:
                plt.plot(occurrences[entry],range(occurrences[entry].__len__()), label=entry)
            plt.legend()

            pass

        if self.graphtype["staple"]:
            print("staple")
            pass

        self.draw()