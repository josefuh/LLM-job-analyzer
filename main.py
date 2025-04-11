import json
import sys
import os
import pandas as pd
from datetime import datetime, timedelta
from PyQt6.QtCore import QDate, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QWidget, QFormLayout, QLineEdit, QPushButton, QScrollArea,
    QDateEdit, QRadioButton, QGroupBox, QVBoxLayout, QButtonGroup, QCheckBox, QMainWindow,
    QLabel, QSpinBox, QHBoxLayout, QTextBrowser, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QProgressBar, QFileDialog, QGridLayout, QSplitter
)
from matplotlib import pyplot as plt

import ApiService
import DataAnalysis
from TextParser import TextParser
import re


class FetchWorker(QThread):
    """Worker thread for fetching data to keep UI responsive"""
    update_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)  # current, total
    finished_signal = pyqtSignal(list)

    def __init__(self, location, start_date, end_date, use_date, max_listings, batch_size=20):
        super().__init__()
        self.location = location
        self.start_date = start_date
        self.end_date = end_date
        self.use_date = use_date
        self.max_listings = max_listings
        self.batch_size = batch_size

    def run(self):
        self.update_signal.emit("Starting batch fetching process...")

        # Calculate number of batches needed
        total_batches = (self.max_listings + self.batch_size - 1) // self.batch_size
        all_saved_paths = []

        for batch in range(total_batches):
            if self.isInterruptionRequested():
                self.update_signal.emit("Fetch operation was canceled.")
                break

            self.update_signal.emit(f"Processing batch {batch + 1} of {total_batches}...")

            try:
                # Initialize API service for this batch
                apiService = ApiService.ApiService(
                    self.location,
                    self.start_date,
                    self.end_date,
                    self.use_date
                )

                # Set batch size for this request
                current_batch_size = min(self.batch_size, self.max_listings - len(all_saved_paths))

                # Update the limit in sources
                for source in apiService.sources.values():
                    if "url" in source and "limit=" in source["url"]:
                        source["url"] = source["url"].replace(
                            f"limit={source['url'].split('limit=')[1].split('&')[0]}",
                            f"limit={current_batch_size}"
                        )

                # Update offset if applicable (for pagination)
                offset = batch * self.batch_size
                for source in apiService.sources.values():
                    if "url" in source and "offset=" not in source["url"] and batch > 0:
                        source["url"] += f"&offset={offset}"
                    elif "url" in source and "offset=" in source["url"] and batch > 0:
                        source["url"] = source["url"].replace(
                            f"offset={source['url'].split('offset=')[1].split('&')[0] if '&' in source['url'].split('offset=')[1] else source['url'].split('offset=')[1]}",
                            f"offset={offset}"
                        )

                # Fetch job listings for this batch
                saved_paths = apiService.load(offset);
                all_saved_paths.extend(saved_paths)

                # Update progress
                self.progress_signal.emit(len(all_saved_paths), self.max_listings)
                self.update_signal.emit(f"Batch {batch + 1} complete. Total listings so far: {len(all_saved_paths)}")

                # Stop if we reached our target or no new listings were found
                if len(saved_paths) == 0 and batch > 0:
                    self.update_signal.emit("No more listings found. Stopping fetch.")
                    break

            except Exception as e:
                import traceback
                self.update_signal.emit(f"Error in batch {batch + 1}: {str(e)}")
                self.update_signal.emit(traceback.format_exc())

        self.update_signal.emit(f"Fetch complete. Total listings retrieved: {len(all_saved_paths)}")
        self.finished_signal.emit(all_saved_paths)


class ListingBrowser(QWidget):
    """Widget for browsing and filtering job listings"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        # Filter controls
        filter_group = QGroupBox("Filter Options")
        filter_layout = QGridLayout()

        # Source filter
        self.source_combo = QComboBox()
        self.source_combo.addItem("All Sources")
        self.source_combo.addItem("Platsbanken")
        self.source_combo.addItem("Indeed")
        self.source_combo.addItem("Other")
        self.source_combo.currentIndexChanged.connect(self.apply_filters)
        filter_layout.addWidget(QLabel("Source:"), 0, 0)
        filter_layout.addWidget(self.source_combo, 0, 1)

        # PE related filter
        self.pe_combo = QComboBox()
        self.pe_combo.addItem("All Listings")
        self.pe_combo.addItem("PE Related Only")
        self.pe_combo.addItem("Non-PE Related Only")
        self.pe_combo.currentIndexChanged.connect(self.apply_filters)
        filter_layout.addWidget(QLabel("PE Content:"), 0, 2)
        filter_layout.addWidget(self.pe_combo, 0, 3)

        # Date range filter
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate(2022, 1, 1))
        self.date_from.dateChanged.connect(self.apply_filters)

        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.dateChanged.connect(self.apply_filters)

        filter_layout.addWidget(QLabel("Date From:"), 1, 0)
        filter_layout.addWidget(self.date_from, 1, 1)
        filter_layout.addWidget(QLabel("Date To:"), 1, 2)
        filter_layout.addWidget(self.date_to, 1, 3)

        # Search box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search in listings...")
        self.search_box.textChanged.connect(self.apply_filters)
        filter_layout.addWidget(QLabel("Search:"), 2, 0)
        filter_layout.addWidget(self.search_box, 2, 1, 1, 3)

        # Export button
        self.export_btn = QPushButton("Export Results")
        self.export_btn.clicked.connect(self.export_results)
        filter_layout.addWidget(self.export_btn, 3, 3)

        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        # Results table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "Date", "Source", "Role", "PE Related"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setSortingEnabled(True)
        self.table.cellDoubleClicked.connect(self.show_listing_detail)
        layout.addWidget(self.table)

        # Details view
        self.details = QTextBrowser()
        self.details.setMinimumHeight(200)
        layout.addWidget(self.details)

        self.setLayout(layout)

    def load_data(self, api_service):
        """Load listing data into the browser"""
        self.api_service = api_service
        self.listings = api_service.get_saved_listings()
        self.parser = TextParser()
        self.all_listings_data = []

        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        # Process and display all listings
        for i, (key, listing_info) in enumerate(self.listings.items()):
            try:
                content = self.api_service.get_listing_content(file_path=listing_info["file_path"])

                # Extract data
                lines = content.split("\n")
                title_line = next((line for line in lines if line.startswith("Title:")), "")
                title = title_line.replace("Title:", "").strip()

                date_line = next((line for line in lines if line.startswith("Date:")), "")
                date_str = date_line.replace("Date:", "").strip()

                description_index = content.find("Description:")
                description = content[
                              description_index + len("Description:"):].strip() if description_index != -1 else ""

                # Parse with TextParser
                parsed = self.parser.parse(title, description, date_str)

                # Store the data
                listing_data = {
                    "id": listing_info["id"],
                    "date_str": date_str,
                    "date": self.parse_date(date_str),
                    "source": listing_info["source"],
                    "role": parsed["role"],
                    "pe_related": parsed["PE"],
                    "pe_categories": parsed["pe_categories"],
                    "content": content,
                    "title": title,
                    "description": description,
                    "file_path": listing_info["file_path"]
                }
                self.all_listings_data.append(listing_data)

                # Add to table
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(listing_data["id"]))
                self.table.setItem(row, 1, QTableWidgetItem(str(listing_data["date"])))
                self.table.setItem(row, 2, QTableWidgetItem(listing_data["source"]))
                self.table.setItem(row, 3, QTableWidgetItem(listing_data["role"]))
                self.table.setItem(row, 4, QTableWidgetItem("Yes" if listing_data["pe_related"] else "No"))

            except Exception as e:
                print(f"Error loading listing {listing_info['file_path']}: {e}")

        self.table.setSortingEnabled(True)
        self.table.sortItems(1, Qt.SortOrder.DescendingOrder)  # Sort by date descending

        # Update source filter with available sources
        self.source_combo.clear()
        self.source_combo.addItem("All Sources")
        sources = set(item["source"] for item in self.all_listings_data)
        for source in sorted(sources):
            self.source_combo.addItem(source)

        # Update date ranges
        if self.all_listings_data:
            min_date = min((item["date"] for item in self.all_listings_data if item["date"]), default=QDate(2022, 1, 1))
            max_date = max((item["date"] for item in self.all_listings_data if item["date"]),
                           default=QDate.currentDate())

            if isinstance(min_date, datetime):
                min_date = QDate(min_date.year, min_date.month, min_date.day)
            if isinstance(max_date, datetime):
                max_date = QDate(max_date.year, max_date.month, max_date.day)

            self.date_from.setDate(min_date)
            self.date_to.setDate(max_date)

        self.apply_filters()

    def parse_date(self, date_str):
        """Convert date string to date object for filtering"""
        if not date_str:
            return None

        try:
            # Try different date formats
            for fmt in ('%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f'):
                try:
                    return datetime.strptime(date_str.split('+')[0].split('Z')[0], fmt)
                except ValueError:
                    continue

            # Try parsing datetime object directly
            if hasattr(date_str, 'year'):
                return date_str

            return None
        except Exception:
            return None

    def apply_filters(self):
        """Apply filters to the table view"""
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        source_filter = self.source_combo.currentText()
        pe_filter = self.pe_combo.currentText()
        date_from = self.date_from.date().toPyDate()
        date_to = self.date_to.date().toPyDate()
        search_text = self.search_box.text().lower()

        for item in self.all_listings_data:
            # Apply source filter
            if source_filter != "All Sources" and item["source"] != source_filter:
                continue

            # Apply PE filter
            if pe_filter == "PE Related Only" and not item["pe_related"]:
                continue
            if pe_filter == "Non-PE Related Only" and item["pe_related"]:
                continue

            # Apply date filter
            if item["date"]:
                item_date = item["date"]
                if isinstance(item_date, datetime):
                    item_date = item_date.date()
                if item_date < date_from or item_date > date_to:
                    continue

            # Apply search filter
            if search_text and search_text not in item["content"].lower():
                continue

            # Add to table
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(item["id"]))
            self.table.setItem(row, 1, QTableWidgetItem(str(item["date"])))
            self.table.setItem(row, 2, QTableWidgetItem(item["source"]))
            self.table.setItem(row, 3, QTableWidgetItem(item["role"]))
            self.table.setItem(row, 4, QTableWidgetItem("Yes" if item["pe_related"] else "No"))

        self.table.setSortingEnabled(True)
        self.parent.add_status(f"Displaying {self.table.rowCount()} of {len(self.all_listings_data)} listings")

    def show_listing_detail(self, row, column):
        """Show details of the selected listing"""
        listing_id = self.table.item(row, 0).text()
        source = self.table.item(row, 2).text()

        # Find the listing
        for item in self.all_listings_data:
            if item["id"] == listing_id and item["source"] == source:
                # Format detailed view
                html = f"<h2>{item['title']}</h2>"
                html += f"<p><b>Source:</b> {item['source']} | <b>Date:</b> {item['date_str']}</p>"
                html += f"<p><b>PE Related:</b> {'Yes' if item['pe_related'] else 'No'}</p>"

                if item['pe_related']:
                    html += "<p><b>PE Categories:</b></p><ul>"
                    for category, present in item['pe_categories'].items():
                        if present:
                            html += f"<li>{category.replace('_', ' ').title()}</li>"
                    html += "</ul>"

                html += "<h3>Description:</h3>"
                # Highlight PE terms in the description
                description = item['description']
                if item['pe_related']:
                    # Get all PE terms
                    all_terms = []
                    for terms in self.parser.pe_terms.values():
                        all_terms.extend(terms)

                    # Highlight each term
                    for term in all_terms:
                        pattern = re.compile(re.escape(term), re.IGNORECASE)
                        description = pattern.sub(f"<span style='background-color: yellow;'>{term}</span>", description)

                html += f"<p>{description.replace(chr(10), '<br>')}</p>"

                self.details.setHtml(html)
                break

    def export_results(self):
        """Export current filtered results to CSV"""
        try:
            filename, _ = QFileDialog.getSaveFileName(self, "Save Results", "", "CSV Files (*.csv)")
            if filename:
                if not filename.endswith('.csv'):
                    filename += '.csv'

                # Collect data from visible rows
                data = []
                for row in range(self.table.rowCount()):
                    row_data = {
                        'ID': self.table.item(row, 0).text(),
                        'Date': self.table.item(row, 1).text(),
                        'Source': self.table.item(row, 2).text(),
                        'Role': self.table.item(row, 3).text(),
                        'PE_Related': self.table.item(row, 4).text()
                    }
                    data.append(row_data)

                # Convert to DataFrame and save
                df = pd.DataFrame(data)
                df.to_csv(filename, index=False)
                self.parent.add_status(f"Exported {len(data)} records to {filename}")
        except Exception as e:
            self.parent.add_status(f"Error exporting data: {str(e)}")


class Main(QMainWindow):
    """ Main class for the program, which extends the QMainWindow
    class to create a GUI containing the form and graphs.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fetch_worker = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Swedish Job Market LLM Analyzer")
        self.setGeometry(100, 50, 1200, 800)

        # Create main widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        main_layout = QVBoxLayout()

        # Create tabs
        self.tabs = QTabWidget()
        self.fetch_tab = QWidget()
        self.analysis_tab = QWidget()
        self.browser_tab = QWidget()

        self.tabs.addTab(self.fetch_tab, "Data Collection")
        self.tabs.addTab(self.analysis_tab, "Analysis")
        self.tabs.addTab(self.browser_tab, "Browse Listings")

        # Setup fetch tab
        self.setup_fetch_tab()

        # Setup analysis tab
        self.setup_analysis_tab()

        # Setup browser tab
        self.setup_browser_tab()

        main_layout.addWidget(self.tabs)

        # Status display
        self.statusBox = QTextBrowser()
        self.statusBox.setMaximumHeight(100)
        main_layout.addWidget(QLabel("Status:"))
        main_layout.addWidget(self.statusBox)

        self.central_widget.setLayout(main_layout)

    def setup_fetch_tab(self):
        fetch_layout = QVBoxLayout()

        # Form group
        form_group = QGroupBox("Data Collection Parameters")
        form_layout = QFormLayout()

        # Location field
        self.locationField = QLineEdit()
        self.locationField.setPlaceholderText("e.g., Stockholm, Göteborg, Malmö")
        form_layout.addRow("Location:", self.locationField)

        # Listings count field
        self.listingsCountField = QSpinBox()
        self.listingsCountField.setMinimum(20)
        self.listingsCountField.setMaximum(2000)
        self.listingsCountField.setValue(200)
        self.listingsCountField.setSingleStep(20)
        form_layout.addRow("Max listings to fetch:", self.listingsCountField)

        # Batch size field
        self.batchSizeField = QSpinBox()
        self.batchSizeField.setMinimum(10)
        self.batchSizeField.setMaximum(50)
        self.batchSizeField.setValue(20)
        self.batchSizeField.setSingleStep(5)
        form_layout.addRow("Batch size:", self.batchSizeField)

        # Date selection
        dateGroupBox = QGroupBox("Date Range")
        dateLayout = QVBoxLayout()

        self.useDate = QCheckBox("Use date range")
        self.useDate.setChecked(True)
        self.useDate.clicked.connect(self.check_box)

        dateFieldsLayout = QHBoxLayout()

        startDateLayout = QVBoxLayout()
        startDateLayout.addWidget(QLabel("Start date:"))
        self.startDate = QDateEdit(calendarPopup=True)
        self.startDate.setMinimumDate(QDate(2015, 1, 1))
        self.startDate.setMaximumDate(QDate.currentDate())
        # Default to Jan 2022 as mentioned in the requirements
        self.startDate.setDate(QDate(2022, 1, 1))
        startDateLayout.addWidget(self.startDate)

        endDateLayout = QVBoxLayout()
        endDateLayout.addWidget(QLabel("End date:"))
        self.endDate = QDateEdit(calendarPopup=True)
        self.endDate.setMinimumDate(QDate(2015, 1, 2))
        self.endDate.setMaximumDate(QDate.currentDate())
        # Set end date to current date
        self.endDate.setDate(QDate.currentDate())
        endDateLayout.addWidget(self.endDate)

        dateFieldsLayout.addLayout(startDateLayout)
        dateFieldsLayout.addLayout(endDateLayout)

        dateLayout.addWidget(self.useDate)
        dateLayout.addLayout(dateFieldsLayout)
        dateGroupBox.setLayout(dateLayout)
        form_layout.addRow(dateGroupBox)

        # API Source selection
        sourceGroup = QGroupBox("Data Sources")
        sourceLayout = QVBoxLayout()

        self.platsbankenCheck = QCheckBox("Platsbanken (Swedish Public Employment Service)")
        self.platsbankenCheck.setChecked(True)
        sourceLayout.addWidget(self.platsbankenCheck)

        self.historicalCheck = QCheckBox("Platsbanken Historical Data")
        self.historicalCheck.setChecked(True)
        sourceLayout.addWidget(self.historicalCheck)

        self.indeedCheck = QCheckBox("Indeed")
        self.indeedCheck.setChecked(False)
        sourceLayout.addWidget(self.indeedCheck)

        self.jobPostingCheck = QCheckBox("Job Posting API")
        self.jobPostingCheck.setChecked(False)
        sourceLayout.addWidget(self.jobPostingCheck)

        sourceGroup.setLayout(sourceLayout)
        form_layout.addRow(sourceGroup)

        form_group.setLayout(form_layout)
        fetch_layout.addWidget(form_group)

        # Progress bar
        self.progressBar = QProgressBar()
        self.progressBar.setMinimum(0)
        self.progressBar.setMaximum(100)
        self.progressBar.setValue(0)
        fetch_layout.addWidget(self.progressBar)

        # Buttons
        button_layout = QHBoxLayout()

        self.fetchButton = QPushButton("Fetch Listings")
        self.fetchButton.clicked.connect(self.fetch_listings)
        button_layout.addWidget(self.fetchButton)

        self.cancelButton = QPushButton("Cancel")
        self.cancelButton.clicked.connect(self.cancel_fetch)
        self.cancelButton.setEnabled(False)
        button_layout.addWidget(self.cancelButton)

        fetch_layout.addLayout(button_layout)

        self.fetch_tab.setLayout(fetch_layout)

    def setup_analysis_tab(self):
        analysis_layout = QVBoxLayout()

        # Graph types selection
        graph_group = QGroupBox("Visualization Options")
        graph_layout = QVBoxLayout()

        self.pieBox = QCheckBox("Pie chart - PE vs Non-PE Distribution")
        self.pieBox.setChecked(True)
        graph_layout.addWidget(self.pieBox)

        self.barBox = QCheckBox("Bar chart - PE Distribution by Role")
        self.barBox.setChecked(True)
        graph_layout.addWidget(self.barBox)

        self.timeBox = QCheckBox("Time series - PE Trends Over Time")
        self.timeBox.setChecked(True)
        graph_layout.addWidget(self.timeBox)

        # Date filter for analysis
        date_layout = QHBoxLayout()

        self.analysis_start_date = QDateEdit(calendarPopup=True)
        self.analysis_start_date.setMinimumDate(QDate(2015, 1, 1))
        self.analysis_start_date.setMaximumDate(QDate.currentDate())
        self.analysis_start_date.setDate(QDate(2022, 1, 1))

        self.analysis_end_date = QDateEdit(calendarPopup=True)
        self.analysis_end_date.setMinimumDate(QDate(2015, 1, 2))
        self.analysis_end_date.setMaximumDate(QDate.currentDate())
        self.analysis_end_date.setDate(QDate.currentDate())

        date_layout.addWidget(QLabel("Analyze From:"))
        date_layout.addWidget(self.analysis_start_date)
        date_layout.addWidget(QLabel("To:"))
        date_layout.addWidget(self.analysis_end_date)

        graph_layout.addLayout(date_layout)

        # Export options
        export_layout = QHBoxLayout()
        self.export_graphs_btn = QPushButton("Export Graphs")
        self.export_graphs_btn.clicked.connect(self.export_graphs)

        self.export_data_btn = QPushButton("Export Analysis Data")
        self.export_data_btn.clicked.connect(self.export_analysis_data)

        export_layout.addWidget(self.export_graphs_btn)
        export_layout.addWidget(self.export_data_btn)

        graph_layout.addLayout(export_layout)

        graph_group.setLayout(graph_layout)
        analysis_layout.addWidget(graph_group)

        # Analysis buttons layout
        buttons_layout = QHBoxLayout()

        # Run analysis button
        self.runAnalysisButton = QPushButton("Run Analysis")
        self.runAnalysisButton.clicked.connect(self.run_analysis)
        buttons_layout.addWidget(self.runAnalysisButton)

        # Re-parse button
        self.reparseButton = QPushButton("Re-parse with Current TextParser")
        self.reparseButton.setToolTip("Re-analyze existing data with the current TextParser implementation")
        self.reparseButton.clicked.connect(self.reparse_data)
        buttons_layout.addWidget(self.reparseButton)

        analysis_layout.addLayout(buttons_layout)

        # Canvas for graphs
        self.canvas = DataAnalysis.DataAnalysis()
        self.canvas.fig.clf()
        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setWidgetResizable(True)
        analysis_layout.addWidget(scroll)

        self.analysis_tab.setLayout(analysis_layout)

    def reparse_data(self):
        """Re-parse existing job listings with the current TextParser without fetching new data"""
        self.runAnalysisButton.setEnabled(False)
        self.reparseButton.setEnabled(False)
        self.statusBox.clear()
        self.add_status("Re-parsing existing listings with current TextParser implementation...")

        try:
            # Initialize ApiService (only used to access saved listings)
            apiService = ApiService.ApiService(
                self.locationField.text(),
                self.startDate.date(),
                self.endDate.date(),
                self.useDate.isChecked()
            )

            # Get all saved listings
            all_listings = apiService.get_saved_listings()

            if not all_listings:
                self.add_status("No saved listings found. Please fetch listings first.")
                self.runAnalysisButton.setEnabled(True)
                self.reparseButton.setEnabled(True)
                return

            self.add_status(f"Found {len(all_listings)} saved listings to re-parse.")

            # Create a new TextParser instance (will use the updated implementation)
            parser = TextParser()
            self.add_status("Created new TextParser instance with current implementation.")

            # Will store the parsed results
            parsed_data = []

            # Get filter parameters
            date_from = self.analysis_start_date.date().toPyDate()
            date_to = self.analysis_end_date.date().toPyDate()

            # Process each saved listing
            processed_count = 0
            for listing_key, listing_info in all_listings.items():
                file_path = listing_info["file_path"]

                # Get the content of the saved listing
                content = apiService.get_listing_content(file_path=file_path)

                # Extract title, description, and date from the content
                try:
                    lines = content.split("\n")
                    title_line = next((line for line in lines if line.startswith("Title:")), "")
                    title = title_line.replace("Title:", "").strip()

                    # Get the date from metadata
                    date_line = next((line for line in lines if line.startswith("Date:")), "")
                    date_str = date_line.replace("Date:", "").strip()

                    # Parse the date for filtering
                    listing_date = None
                    try:
                        for fmt in ('%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f'):
                            try:
                                listing_date = datetime.strptime(date_str.split('+')[0].split('Z')[0], fmt).date()
                                break
                            except ValueError:
                                continue
                    except:
                        # If we can't parse the date, include it anyway
                        pass

                    # Apply date filter if we have a valid date
                    if listing_date and (listing_date < date_from or listing_date > date_to):
                        continue

                    # Get description (everything after "Description:")
                    description_index = content.find("Description:")
                    description = content[
                                  description_index + len("Description:"):].strip() if description_index != -1 else ""

                    # Parse the extracted information with the current TextParser
                    parsed_result = parser.parse(title, description, date_str)

                    # Add to results
                    parsed_data.append(json.dumps(parsed_result))
                    processed_count += 1

                    # Show periodic progress updates
                    if processed_count % 50 == 0:
                        self.add_status(f"Re-parsed {processed_count} listings so far...")

                except Exception as e:
                    self.add_status(f"Error re-parsing listing {file_path}: {e}")

            # Display analysis results
            if parsed_data:
                self.add_status(f"Successfully re-parsed {len(parsed_data)} job listings.")
                self.canvas.load_data(parsed_data, {
                    "pie": self.pieBox.isChecked(),
                    "time": self.timeBox.isChecked(),
                    "bar": self.barBox.isChecked()
                })

                try:
                    self.canvas.plot_data()
                    self.add_status("Re-parsing complete. Graphs have been updated with new results.")
                except Exception as e:
                    self.add_status(f"Error generating graphs: {e}")
                    import traceback
                    self.add_status(traceback.format_exc())
            else:
                self.add_status("No data could be re-parsed or all listings were filtered out.")

        except Exception as e:
            self.add_status(f"Error during re-parsing: {e}")
            import traceback
            self.add_status(traceback.format_exc())

        self.runAnalysisButton.setEnabled(True)
        self.reparseButton.setEnabled(True)

    def setup_browser_tab(self):
        browser_layout = QVBoxLayout()

        # Create the browser widget
        self.listing_browser = ListingBrowser(self)
        browser_layout.addWidget(self.listing_browser)

        # Refresh button
        self.refresh_browser_btn = QPushButton("Refresh Listings")
        self.refresh_browser_btn.clicked.connect(self.refresh_browser)
        browser_layout.addWidget(self.refresh_browser_btn)

        self.browser_tab.setLayout(browser_layout)

    def resizeEvent(self, event):
        """
        Window event handler called when the window is resized.
        Is used to resize the canvas that the graphs are printed
        in.
        :param event: reSizeEvent
        """
        if hasattr(self, 'canvas'):
            self.canvas.resize(self.analysis_tab.size())
        super().resizeEvent(event)

    def check_box(self):
        """ Method for enabling or disabling the
        start and end date fields when clicking the
        use date button.
        """
        if self.useDate.isChecked():
            self.startDate.setEnabled(True)
            self.endDate.setEnabled(True)
        else:
            self.startDate.setEnabled(False)
            self.endDate.setEnabled(False)

    def add_status(self, message):
        """Add a message to the status box"""
        self.statusBox.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        # Scroll to the bottom
        scrollbar = self.statusBox.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        # Refresh UI
        QApplication.processEvents()

    def fetch_listings(self):
        """Method for fetching and saving job listings without analyzing them"""
        self.fetchButton.setEnabled(False)
        self.cancelButton.setEnabled(True)
        self.progressBar.setValue(0)
        self.statusBox.clear()
        self.add_status("Starting to fetch job listings...")

        try:
            # Get parameters
            location = self.locationField.text()
            max_listings = self.listingsCountField.value()
            batch_size = self.batchSizeField.value()

            # Create and start the worker thread
            self.fetch_worker = FetchWorker(
                location,
                self.startDate.date(),
                self.endDate.date(),
                self.useDate.isChecked(),
                max_listings,
                batch_size
            )

            # Connect signals
            self.fetch_worker.update_signal.connect(self.add_status)
            self.fetch_worker.progress_signal.connect(self.update_progress)
            self.fetch_worker.finished_signal.connect(self.fetch_completed)
            self.fetch_worker.finished.connect(self.fetch_worker_done)

            # Start fetching
            self.fetch_worker.start()

        except Exception as e:
            self.add_status(f"Error initiating fetch: {str(e)}")
            import traceback
            self.add_status(traceback.format_exc())
            self.fetchButton.setEnabled(True)
            self.cancelButton.setEnabled(False)

    def update_progress(self, current, total):
        """Update progress bar"""
        percentage = min(int((current / total) * 100), 100)
        self.progressBar.setValue(percentage)

    def fetch_completed(self, saved_paths):
        """Called when fetch is complete"""
        self.add_status(f"Fetch completed. {len(saved_paths)} listings saved.")
        self.tabs.setCurrentIndex(1)  # Switch to analysis tab
        self.refresh_browser()

    def fetch_worker_done(self):
        """Called when worker thread is finished"""
        self.fetchButton.setEnabled(True)
        self.cancelButton.setEnabled(False)
        self.fetch_worker = None

    def cancel_fetch(self):
        """Cancel the fetching process"""
        if self.fetch_worker and self.fetch_worker.isRunning():
            self.add_status("Cancelling fetch operation...")
            self.fetch_worker.requestInterruption()

    def refresh_browser(self):
        """Refresh the listing browser with current data"""
        try:
            # Initialize ApiService to access saved listings
            api_service = ApiService.ApiService(
                self.locationField.text(),
                self.startDate.date(),
                self.endDate.date(),
                self.useDate.isChecked()
            )

            # Load data into the browser
            self.add_status("Loading listings into browser...")
            self.listing_browser.load_data(api_service)
            self.add_status("Listings loaded successfully")

            # Switch to browser tab
            self.tabs.setCurrentIndex(2)

        except Exception as e:
            self.add_status(f"Error loading listings: {str(e)}")
            import traceback
            self.add_status(traceback.format_exc())

    def run_analysis(self):
        """Run analysis on the job listings"""
        self.add_status("Starting analysis...")

        # Get graph types
        graph_types = {
            "pie": self.pieBox.isChecked(),
            "bar": self.barBox.isChecked(),
            "time": self.timeBox.isChecked()
        }

        # Get date filters
        start_date = self.analysis_start_date.date().toPyDate()
        end_date = self.analysis_end_date.date().toPyDate()

        # Create a parser
        parser = TextParser()

        # Get API service to access raw data
        api_service = ApiService.ApiService("", QDate(), QDate(), False)  # Create with default params
        raw_listings = api_service.get_saved_listings()

        # Process and parse all listings for analysis directly
        analysis_data = []

        self.add_status(f"Processing {len(raw_listings)} listings...")

        for key, listing_info in raw_listings.items():
            try:
                # Get the raw content of the listing
                content = api_service.get_listing_content(file_path=listing_info["file_path"])

                # Extract data fields from content
                lines = content.split("\n")
                title_line = next((line for line in lines if line.startswith("Title:")), "")
                title = title_line.replace("Title:", "").strip()

                date_line = next((line for line in lines if line.startswith("Date:")), "")
                date_str = date_line.replace("Date:", "").strip()

                # Extract description
                description_index = content.find("Description:")
                description = content[
                              description_index + len("Description:"):].strip() if description_index != -1 else ""

                # Parse the date
                listing_date = None
                try:
                    for fmt in ('%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f'):
                        try:
                            listing_date = datetime.strptime(date_str.split('+')[0].split('Z')[0], fmt)
                            break
                        except ValueError:
                            continue
                except Exception as e:
                    self.add_status(f"Error parsing date in listing {listing_info['id']}: {e}")

                # Apply date filter if date is available
                if listing_date:
                    listing_py_date = listing_date.date()
                    if listing_py_date < start_date or listing_py_date > end_date:
                        continue

                # Parse the listing content to detect role and PE skills
                parsed = parser.parse(title, description, date_str)

                # Add to analysis data as JSON string
                analysis_data.append(json.dumps(parsed))

            except Exception as e:
                self.add_status(f"Error processing listing {listing_info['file_path']}: {e}")
                continue

        # Update the data analysis with the freshly parsed data
        self.canvas.load_data(analysis_data, graph_types)
        self.canvas.plot_data()

        self.add_status(f"Analysis complete. Successfully analyzed {len(analysis_data)} listings.")
        
    def export_graphs(self):
        """Export the current graphs to image files"""
        try:
            directory = QFileDialog.getExistingDirectory(self, "Select Directory to Save Graphs")
            if directory:
                self.add_status("Exporting graphs...")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

                # Check if canvas exists and has a figure
                if not hasattr(self, 'canvas') or not hasattr(self.canvas, 'fig'):
                    self.add_status("No graphs available to export")
                    return

                # Check if there are any axes in the figure
                if not hasattr(self.canvas.fig, 'axes') or len(self.canvas.fig.axes) == 0:
                    self.add_status("No graph data available to export")
                    return

                # Get the number of axes available
                num_axes = len(self.canvas.fig.axes)
                self.add_status(f"Found {num_axes} graphs to export")

                # Export individual graphs if they exist
                if self.pieBox.isChecked() and num_axes >= 3:
                    try:
                        pie_path = os.path.join(directory, f"pe_distribution_{timestamp}.png")
                        # Create a new figure for just this plot
                        pie_fig = plt.figure(figsize=(8, 6))
                        pie_ax = pie_fig.add_subplot(111)

                        # Copy content from the original axis
                        for artist in self.canvas.fig.axes[2].get_children():
                            if hasattr(artist, 'get_data'):
                                x, y = artist.get_data()
                                pie_ax.plot(x, y, color=artist.get_color(), linestyle=artist.get_linestyle())

                        # Copy the title and labels
                        pie_ax.set_title(self.canvas.fig.axes[2].get_title())

                        pie_fig.savefig(pie_path, bbox_inches='tight', dpi=300)
                        plt.close(pie_fig)
                        self.add_status(f"Saved pie chart to {pie_path}")
                    except Exception as e:
                        self.add_status(f"Error saving pie chart: {str(e)}")

                if self.barBox.isChecked() and num_axes >= 2:
                    try:
                        bar_path = os.path.join(directory, f"role_distribution_{timestamp}.png")
                        # Create a new figure for just this plot
                        bar_fig = plt.figure(figsize=(8, 6))
                        bar_ax = bar_fig.add_subplot(111)

                        # Copy content from the original axis
                        for artist in self.canvas.fig.axes[1].get_children():
                            if hasattr(artist, 'get_data'):
                                x, y = artist.get_data()
                                bar_ax.plot(x, y, color=artist.get_color(), linestyle=artist.get_linestyle())

                        # Copy the title and labels
                        bar_ax.set_title(self.canvas.fig.axes[1].get_title())

                        bar_fig.savefig(bar_path, bbox_inches='tight', dpi=300)
                        plt.close(bar_fig)
                        self.add_status(f"Saved bar chart to {bar_path}")
                    except Exception as e:
                        self.add_status(f"Error saving bar chart: {str(e)}")

                if self.timeBox.isChecked() and num_axes >= 1:
                    try:
                        time_path = os.path.join(directory, f"time_trends_{timestamp}.png")
                        # Create a new figure for just this plot
                        time_fig = plt.figure(figsize=(8, 6))
                        time_ax = time_fig.add_subplot(111)

                        # Copy content from the original axis
                        for artist in self.canvas.fig.axes[0].get_children():
                            if hasattr(artist, 'get_data'):
                                x, y = artist.get_data()
                                time_ax.plot(x, y, color=artist.get_color(), linestyle=artist.get_linestyle())

                        # Copy the title and labels
                        time_ax.set_title(self.canvas.fig.axes[0].get_title())

                        time_fig.savefig(time_path, bbox_inches='tight', dpi=300)
                        plt.close(time_fig)
                        self.add_status(f"Saved time series to {time_path}")
                    except Exception as e:
                        self.add_status(f"Error saving time series: {str(e)}")

                # Save combined figure
                try:
                    combined_path = os.path.join(directory, f"all_charts_{timestamp}.png")
                    self.canvas.fig.savefig(combined_path, bbox_inches='tight', dpi=300)
                    self.add_status(f"Saved combined chart to {combined_path}")
                except Exception as e:
                    self.add_status(f"Error saving combined chart: {str(e)}")

        except Exception as e:
            self.add_status(f"Error exporting graphs: {str(e)}")
            import traceback
            self.add_status(traceback.format_exc())


    def export_analysis_data(self):
        """Export the analyzed data to CSV"""
        try:
            filename, _ = QFileDialog.getSaveFileName(self, "Save Analysis Data", "", "CSV Files (*.csv)")
            if filename:
                if not filename.endswith('.csv'):
                    filename += '.csv'

                # Initialize ApiService
                apiService = ApiService.ApiService(
                    self.locationField.text(),
                    self.startDate.date(),
                    self.endDate.date(),
                    self.useDate.isChecked()
                )

                # Get all listings
                all_listings = apiService.get_saved_listings()
                parser = TextParser()

                # Process each listing
                data = []
                for listing_key, listing_info in all_listings.items():
                    try:
                        # Get content
                        content = apiService.get_listing_content(file_path=listing_info["file_path"])

                        # Extract data
                        lines = content.split("\n")
                        title_line = next((line for line in lines if line.startswith("Title:")), "")
                        title = title_line.replace("Title:", "").strip()

                        date_line = next((line for line in lines if line.startswith("Date:")), "")
                        date_str = date_line.replace("Date:", "").strip()

                        description_index = content.find("Description:")
                        description = content[description_index + len(
                            "Description:"):].strip() if description_index != -1 else ""

                        # Parse with TextParser
                        parsed = parser.parse(title, description, date_str)

                        # Build row data
                        row = {
                            'ID': listing_info["id"],
                            'Source': listing_info["source"],
                            'Date': date_str,
                            'Role': parsed["role"],
                            'PE_Related': 'Yes' if parsed["PE"] else 'No'
                        }

                        # Add PE categories
                        for category, present in parsed["pe_categories"].items():
                            row[f'Category_{category}'] = 'Yes' if present else 'No'

                        data.append(row)
                    except Exception as e:
                        self.add_status(f"Error processing listing {listing_info['file_path']}: {e}")

                # Create and save dataframe
                if data:
                    df = pd.DataFrame(data)
                    df.to_csv(filename, index=False)
                    self.add_status(f"Exported {len(data)} records to {filename}")
                else:
                    self.add_status("No data to export")

        except Exception as e:
            self.add_status(f"Error exporting data: {str(e)}")
            import traceback
            self.add_status(traceback.format_exc())


if __name__ == '__main__':
    app = QApplication([])
    window = Main()
    window.show()
    sys.exit(app.exec())