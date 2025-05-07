import matplotlib
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QSizePolicy
import json
from datetime import datetime
from collections import Counter, defaultdict

matplotlib.use('QtAgg')


class DataAnalysis(FigureCanvasQTAgg):
    def __init__(self, results=None, graphtype=None):
        self.fig = plt.figure(figsize=(10, 16), dpi=100)
        super().__init__(self.fig)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(QSize(600, 800))

        self.graphtype = graphtype or {"pie": True, "bar": True, "time": True}
        self.results = results or []
        self.processed_data = None

        plt.style.use('seaborn-v0_8-whitegrid')
        self.colors = {'pe': '#e63946', 'non_pe': '#457b9d', 'llm_tools': '#ab83a1'}

        # initial axes with placeholders
        self.axes = []
        self.setup_initial_axes()

    def sizeHint(self):
        return QSize(800, 1000)

    def setup_initial_axes(self):
        self.fig.clear()
        self.axes = []

        for i in range(3):
            ax = self.fig.add_subplot(4, 1, i + 1)
            ax.text(0.5, 0.5, f"Graph {i + 1} will appear after analysis is run",
                    ha='center', va='center', fontsize=12)
            ax.axis('off')
            self.axes.append(ax)

        self.fig.tight_layout(pad=4.0)
        self.draw()

    def load_data(self, results, graphtype):
        self.graphtype = graphtype
        self.results = results

    def _process_data(self):
        # initialize data structures
        data = {
            'all_roles': [],
            'pe_roles': [],
            'dates': [],
            'pe_dates': [],
            'non_pe_dates': [],
            'pe_categories': defaultdict(list)
        }

        if not self.results:
            return False

        # process each job listing
        for item in self.results:
            try:
                # parse data
                raw = json.loads(item) if isinstance(item, str) else item

                role = raw.get('role', '').lower().strip()
                is_pe = raw.get('PE', False)

                # truncate long role names
                if len(role) > 25:
                    key_terms = ['utvecklare', 'developer', 'engineer', 'architect']
                    for term in key_terms:
                        if term in role:
                            idx = role.find(term)
                            role = role[max(0, idx - 5):min(len(role), idx + len(term) + 5)]
                            break

                data['all_roles'].append(role)
                if is_pe:
                    data['pe_roles'].append(role)

                # handle date
                date_str = raw.get('date', '')
                date_obj = None

                if isinstance(date_str, datetime):
                    date_obj = date_str
                elif date_str:
                    try:
                        date_obj = datetime.fromisoformat(str(date_str).replace('Z', '+00:00'))
                    except (ValueError, TypeError):
                        continue

                if date_obj:
                    data['dates'].append(date_obj)
                    if is_pe:
                        data['pe_dates'].append(date_obj)
                    else:
                        data['non_pe_dates'].append(date_obj)

                # add pe categories
                if is_pe:
                    for category, present in raw.get('pe_categories', {}).items():
                        if present:
                            data['pe_categories'][category].append(role)
            except:
                continue

        self.processed_data = data
        return len(data['all_roles']) > 0

    def plot_data(self):
        self.fig.clear()
        self.axes = []

        # determine which graphs to show
        plots_to_show = []
        if self.graphtype.get("time", True): plots_to_show.append("time")
        if self.graphtype.get("bar", True): plots_to_show.append("bar")
        if self.graphtype.get("pie", True): plots_to_show.append("pie")

        if not plots_to_show:
            plots_to_show = ["pie"]  # default to pie if nothing selected

        # create axes for each plot
        for i, plot_type in enumerate(plots_to_show):
            ax = self.fig.add_subplot(len(plots_to_show), 1, i + 1)
            self.axes.append(ax)

        # process data - if fails, show error and return
        if not self._process_data():
            for ax in self.axes:
                ax.clear()
                ax.text(0.5, 0.5, "No data available to visualize",
                        ha='center', va='center', fontsize=14)
                ax.axis('off')
            self.fig.tight_layout()
            self.draw()
            return

        # create each plot
        for i, plot_type in enumerate(plots_to_show):
            try:
                if plot_type == "time":
                    self._plot_time_series(self.axes[i])
                elif plot_type == "bar":
                    self._plot_bar_chart(self.axes[i])
                elif plot_type == "pie":
                    self._plot_pie_chart(self.axes[i])
            except Exception as e:
                self.axes[i].clear()
                self.axes[i].text(0.5, 0.5, f"Error creating {plot_type} chart",
                                  ha='center', va='center', fontsize=14, color='red')
                self.axes[i].axis('off')

        # adjust layout and draw
        self.fig.tight_layout(pad=3.0)
        self.draw()

    def _plot_time_series(self, ax):
        # plot time trends
        dates = self.processed_data['dates']
        if not dates:
            ax.text(0.5, 0.5, "No date data available", ha='center', va='center')
            ax.axis('off')
            return

        # group dates by month
        pe_dates = defaultdict(int)
        non_pe_dates = defaultdict(int)

        for date in self.processed_data['pe_dates']:
            month_key = datetime(date.year, date.month, 1)
            pe_dates[month_key] += 1

        for date in self.processed_data['non_pe_dates']:
            month_key = datetime(date.year, date.month, 1)
            non_pe_dates[month_key] += 1

        # get sorted unique dates
        all_dates = sorted(set(list(pe_dates.keys()) + list(non_pe_dates.keys())))

        # prepare data for plotting
        pe_values = [pe_dates.get(date, 0) for date in all_dates]
        non_pe_values = [non_pe_dates.get(date, 0) for date in all_dates]

        pe_cumulative = np.cumsum(pe_values)
        non_pe_cumulative = np.cumsum(non_pe_values)

        # plot data
        ax.plot(all_dates, pe_values, label='PE Related',
                color=self.colors['pe'], linewidth=2, marker='o', markersize=4)
        ax.plot(all_dates, non_pe_values, label='Non-PE Related',
                color=self.colors['non_pe'], linewidth=2, marker='o', markersize=4)

        # trend line
        all_dates_i = mdates.date2num(all_dates)

        pe_trend = np.polyfit(all_dates_i, pe_values, 1)
        non_pe_trend = np.polyfit(all_dates_i, non_pe_values,1)

        ax.plot(all_dates,np.poly1d(pe_trend)(all_dates_i), label='PE Trend', color=self.colors['pe'], linestyle=':')
        ax.plot(all_dates,np.poly1d(non_pe_trend)(all_dates_i), label='non-PE Trend', color=self.colors['non_pe'], linestyle=':')

        # add formatting
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

        # add reference lines for major AI releases
        key_events = [
            (datetime(2022, 11, 30), 'ChatGPT'),
            (datetime(2023, 3, 14), 'GPT-4')
        ]

        for date, label in key_events:
            if min(all_dates) <= date <= max(all_dates):
                ax.axvline(x=date, color='gray', linestyle=':', alpha=0.7)
                ax.text(date, ax.get_ylim()[1] * 0.9, label, rotation=90, fontsize=8)

        # add labels
        ax.set_xlabel('Date')
        #ax.set_ylabel('Cumulative Listings')
        ax.set_ylabel('Number Of Listings')
        ax.set_title('PE Skills Demand Over Time (RQ3)')
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper left')

        # store for export
        self.pe_time_data = [all_dates, pe_cumulative]

    def _plot_pe_time_series(self, ax):
        # plot time trends for PE only
        dates = self.processed_data['dates']
        if not dates:
            ax.text(0.5, 0.5, "No date data available", ha='center', va='center')
            ax.axis('off')
            return

        # group dates by month
        pe_dates = defaultdict(int)

        for date in self.processed_data['pe_dates']:
            month_key = datetime(date.year, date.month, 1)
            pe_dates[month_key] += 1

        # get sorted unique dates
        all_dates = sorted(pe_dates.keys())
        if not all_dates:
            ax.text(0.5, 0.5, "No PE data available", ha='center', va='center')
            ax.axis('off')
            return

        # prepare data for plotting
        pe_values = [pe_dates.get(date, 0) for date in all_dates]
        pe_cumulative = np.cumsum(pe_values)

        # plot data
        ax.plot(all_dates, pe_values, label='PE Related',
                color=self.colors['pe'], linewidth=2, marker='o', markersize=4)

        # trend line
        all_dates_i = mdates.date2num(all_dates)

        pe_trend = np.polyfit(all_dates_i, pe_values, 1)

        ax.plot(all_dates, np.poly1d(pe_trend)(all_dates_i), label='PE Trend', color=self.colors['pe'], linestyle=':')

        # add formatting
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

        # reference lines
        key_events = [
            (datetime(2022, 11, 30), 'ChatGPT'),
            (datetime(2023, 3, 14), 'GPT-4')
        ]

        for date, label in key_events:
            if min(all_dates) <= date <= max(all_dates):
                ax.axvline(x=date, color='gray', linestyle=':', alpha=0.7)
                ax.text(date, ax.get_ylim()[1] * 0.9, label, rotation=90, fontsize=8)

        # labels
        ax.set_xlabel('Date')
        ax.set_ylabel('Number Of PE Listings')
        ax.set_title('PE Skills Demand Trend (PE Only)')
        ax.grid(True, alpha=0.3)

    def _plot_bar_chart(self, ax):
        # plot role distribution
        all_roles = Counter(self.processed_data['all_roles'])
        pe_roles = Counter(self.processed_data['pe_roles'])

        # get top roles
        sorted_roles = [role for role, _ in all_roles.most_common(8)]

        if not sorted_roles:
            ax.text(0.5, 0.5, "No role data available", ha='center', va='center')
            ax.axis('off')
            return

        # prepare data
        pe_values = [pe_roles.get(role, 0) for role in sorted_roles]
        non_pe_values = [all_roles.get(role, 0) - pe_roles.get(role, 0) for role in sorted_roles]

        # Add the new PE-only roles data
        self.bar_pe_names = [role for role, _ in pe_roles.most_common(10)]
        bar_pe_value = [pe_roles.get(role, 0) for role in self.bar_pe_names]
        self.bar_pe_counter = np.arange(len(bar_pe_value))

        # store for export
        self.bar_names = sorted_roles
        self.bar_values = [pe_values, non_pe_values, bar_pe_value]

        # create chart
        x = np.arange(len(sorted_roles))
        self.bar_x_value = x

        ax.bar(x, non_pe_values, 0.35, label='Non-PE', color=self.colors['non_pe'])
        ax.bar(x, pe_values, 0.35, bottom=non_pe_values, label='PE', color=self.colors['pe'])

        # add percentage labels
        for i, role in enumerate(sorted_roles):
            total = all_roles.get(role, 0)
            pe_count = pe_roles.get(role, 0)
            if total > 0 and pe_count > 0:
                percentage = (pe_count / total) * 100
                ax.text(i, non_pe_values[i] + pe_values[i] + 0.3, f"{percentage:.1f}%",
                        ha='center', va='bottom', fontsize=9, color=self.colors['pe'])

        # add labels
        ax.set_xlabel('Job Role')
        ax.set_ylabel('Number of Listings')
        ax.set_title('Distribution of PE Skills by Role (RQ2)')
        ax.set_xticks(x)
        ax.set_xticklabels(sorted_roles, rotation=45, ha='right')
        ax.grid(True, alpha=0.3, axis='y')
        ax.legend()

    def _plot_pie_chart(self, ax):
        # plot overall distribution

        pe_count = len(self.processed_data['pe_roles'])
        non_pe_count = len(self.processed_data['all_roles']) - pe_count
        total = pe_count + non_pe_count

        if total == 0:
            ax.text(0.5, 0.5, "No data for pie chart", ha='center', va='center')
            ax.axis('off')
            return

        # create pie chart
        labels = ['Non-PE Related', 'PE Related']
        sizes = [non_pe_count, pe_count]
        colors = [self.colors['non_pe'], self.colors['pe']]

        self.pie_sizes = sizes  # store for export

        ax.pie(sizes, labels=labels, colors=colors,
               autopct=lambda pct: f"{pct:.1f}%\n({round(total * pct / 100)})",
               startangle=90, wedgeprops={'edgecolor': 'w', 'linewidth': 1})

        ax.set_title('PE Skills in Job Listings (RQ1)')

        # add category breakdown if relevant
        if pe_count > 0:
            categories = self.processed_data['pe_categories']
            if categories:
                counts = {k: len(v) for k, v in categories.items() if v}
                if counts:
                    # create a simple text summary
                    text = "PE Categories:\n"

                    for category, count in counts.items():
                        pct = (count / pe_count) * 100
                        text += f"• {category.replace('_', ' ').title()}: {pct:.1f}% ({count})\n"

                    ax.text(1.1, 0.5, text, transform=ax.transAxes, fontsize=9,
                            verticalalignment='center',
                            bbox=dict(boxstyle='round', fc='white', alpha=0.8))


    def _plot_prop_norm_pe_cumulative_time_series(self, ax):
        dates = self.processed_data['dates']
        pe_dates = self.processed_data['pe_dates']

        if not dates:
            ax.text(0.5, 0.5, "No date data available", ha='center', va='center')
            ax.axis('off')
            return

        total_by_month = defaultdict(int)
        for d in dates:
            month = datetime(d.year, d.month, 1)
            total_by_month[month] += 1

        pe_by_month = defaultdict(int)
        for d in pe_dates:
            month = datetime(d.year, d.month, 1)
            pe_by_month[month] += 1

        all_months = sorted(set(total_by_month) | set(pe_by_month))
        if not all_months:
            ax.text(0.5, 0.5, "No PE or date data available", ha='center', va='center')
            ax.axis('off')
            return

        prop = []
        for m in all_months:
            total = total_by_month.get(m, 0)
            pe    = pe_by_month.get(m, 0)
            # avoid division by zero
            prop.append(pe / total if total > 0 else 0.0)

        cum_prop = np.cumsum(prop)

        ax.plot(all_months, cum_prop,
                label='Cumulative Proportion PE',
                color=self.colors['pe'], linewidth=2, marker='o', markersize=4)

        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

        # Reference lines
        key_events = [
            (datetime(2022, 11, 30), 'ChatGPT'),
            (datetime(2023, 3, 14),  'GPT-4')
        ]
        for date, label in key_events:
            if all_months[0] <= date <= all_months[-1]:
                ax.axvline(x=date, color='gray', linestyle=':', alpha=0.7)
                ax.text(date, ax.get_ylim()[1] * 0.9, label,
                        rotation=90, fontsize=8, va='top')

        ax.set_xlabel('Month')
        ax.set_ylabel('Cumulative Proportion of PE')
        ax.set_title('Normalized PE Skills Demand Trend')
        ax.legend(loc='upper left')
        ax.grid(True, alpha=0.3)
















