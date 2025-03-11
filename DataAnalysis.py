import matplotlib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
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
    graphtype: str, optional
        The graph type assigned by the user, by default None

    """

    def __init__(self, results, graphtype):
        self.fig, (self.pie, self.bar, self.time) = plt.subplots(3, 1,sharey=False, sharex=False)

        super().__init__(self.fig)

        self.graphtype = graphtype
        self.results = results

    def plot_data(self):
        """ Function used to create and return the graphs to the GUI

        :return: created graphs
        """

        plt.clf()
        y = np.array([35, 25])

        plt.subplot(3, 1, 1)
        self.time = plt.plot(1, 1, y)
        plt.subplot(3, 1, 2)
        self.bar = plt.bar(y,height=50)
        plt.subplot(3, 1, 3)
        self.pie = plt.pie(y, labels=self.results)


        if self.graphtype == "" or self.graphtype == "pie":
            pass

        if self.graphtype == "" or self.graphtype == "bar":
            pass

        if self.graphtype == "" or self.graphtype == "time":
            pass
