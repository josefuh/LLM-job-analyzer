from ftplib import all_errors

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

        self.fig, (self.pie, self.bar, self.time) = plt.subplots(3, 1, sharey=False, sharex=False, figsize=(8, 12))
        self.fig.tight_layout(h_pad=15.5) # TODO: padding mellan grafer, höj om det behövs!
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

        plt.cla()
        plt.clf()

        all_skills = []
        llm_skills = []

        dates = []
        for json_data in self.results:
            raw = json.loads(''.join(json_data))

            for skill in raw['skills']:

                if skill['LLMRelated'] == "yes":
                    llm_skills.append(skill['keyword'])
                all_skills.append(skill['keyword'])
                dates.append(raw['date'])

        data = {"skills": all_skills, "date": dates}

        if not self.graphtype["pie"] and not self.graphtype["time"] and not self.graphtype["bar"]:
            return

        if self.graphtype["time"]:
            plt.subplot(3, 1, 1)

            dataframe = pd.DataFrame(data)
            dataframe['date'] = pd.to_datetime(dataframe['date'])
            dataframe = dataframe.sort_values(by='date')

            dataframe.reset_index()
            occurrences = {}
            for skill in set(all_skills):
                occurrences[skill] = []

            for index, row in dataframe.iterrows():
                occurrences[row['skills']].append(row['date'])

            for entry in occurrences:
                style = "dotted"
                if entry in llm_skills:
                    style = "solid"

                plt.plot(occurrences[entry], range(occurrences[entry].__len__()), label=entry, ls=style)
            plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.25),
                       fancybox=True, shadow=True, ncol=10)
            plt.savefig("time.jpg")
        if self.graphtype["bar"]:
            plt.subplot(3, 1, 2)
            dataframe = pd.DataFrame(data)
            total = dataframe.groupby(dataframe['skills']).value_counts().values.sum()
            total_frame = dataframe.groupby(['skills']).count().values

            colors = []
            d = {}
            unique = list(set(all_skills))
            for skill in unique:
                d[skill] = 0
                if skill in llm_skills:
                    colors.append("tab:red")
                    continue
                colors.append("tab:blue")

            for skill in dataframe['skills']:
                d[skill] += 1

            #plt.bar(unique,[x for l in total_frame for x in l], width=0.3, color=colors)
            plt.bar(*zip(*d.items()), width=0.3, color=colors)
            plt.xticks(rotation=90, fontsize=10)
            plt.savefig("bar.jpg")
        if self.graphtype["pie"]:
            plt.subplot(3, 1, 3)
            temp = [len([item for item in all_skills if item not in llm_skills]), len(llm_skills)]
            total = sum(temp)

            dataframe = np.array(temp)
            plt.pie(dataframe, labels=["non-llm skills", "llm skills"],
                    autopct=(lambda x: '{:.1f}%\n{:.0f}'.format(x, total * x / 100)))
            plt.savefig("pie.jpg")
            # extra pie chart för att se alla skills
            """
            plt.subplot(3, 2, 4)

            dataframe = pd.DataFrame(data)
            total = dataframe.groupby(dataframe['skills']).value_counts().values.sum()
            total_frame = dataframe.groupby(['skills']).count().values
            #total = w.sum()

            unique = list(set(all_skills))
            plt.pie([x for l in total_frame for x in l],labels=unique,autopct=(lambda x: '{:.1f}%\n{:.0f}'.format(x, total*x/100)))
            #plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))
            """

        self.draw()
