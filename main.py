import json
import sys
import os
import pandas as pd
from datetime import datetime
from PyQt6.QtCore import QDate, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QWidget, QFormLayout, QLineEdit, QPushButton, QScrollArea,
    QDateEdit, QGroupBox, QVBoxLayout, QHBoxLayout, QTextBrowser, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QProgressBar,
    QFileDialog, QGridLayout, QCheckBox, QMainWindow, QLabel, QSpinBox,
    QMessageBox
)
from matplotlib import pyplot as plt
import matplotlib.dates as mdates
import re

import ApiService
import DataAnalysis
from TextParser import TextParser


class FetchWorker(QThread):
    update_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)
    finished_signal = pyqtSignal(list)

    def __init__(self, location, start_date, end_date, use_date, max_listings, batch_size=20, sources=None):
        super().__init__()
        self.location = location
        self.start_date = start_date
        self.end_date = end_date
        self.use_date = use_date
        self.max_listings = max_listings
        self.batch_size = batch_size
        self.sources = sources

    def run(self):
        self.update_signal.emit("Starting fetch process...")

        try:

            api_service = ApiService.ApiService(
                self.location,
                self.start_date,
                self.end_date,
                self.use_date,
                self.sources
            )

            if self.max_listings <= 20:
                time_segments = 2
                offset_steps = 1
            elif self.max_listings <= 100:
                time_segments = 3
                offset_steps = 2
            else:
                time_segments = 4
                offset_steps = 3

            self.update_signal.emit(
                f"Fetching listings with {time_segments} time segments and {offset_steps} pagination steps...")

            saved_paths = api_service.load(
                batch_offset=0,
                time_segments=time_segments,
                offset_steps=offset_steps,
                max_listings=self.max_listings
            )

            self.progress_signal.emit(len(saved_paths), self.max_listings)

            if self.isInterruptionRequested():
                self.update_signal.emit("Fetch canceled during processing")

        except Exception as e:
            self.update_signal.emit(f"Error in fetch process: {str(e)}")
            saved_paths = []

        self.update_signal.emit(f"Fetch complete: {len(saved_paths)} listings")
        self.finished_signal.emit(saved_paths)

class ListingBrowser(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.all_listings_data = []
        self.parent = parent
        self.parser = TextParser()
        self.api_service = None
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        # Filter options
        filter_group = QGroupBox("Filter Options")
        filter_layout = QGridLayout()

        # Source filter
        self.source_combo = QComboBox()
        self.source_combo.addItem("All Sources")
        self.source_combo.currentIndexChanged.connect(self.apply_filters)
        filter_layout.addWidget(QLabel("Source:"), 0, 0)
        filter_layout.addWidget(self.source_combo, 0, 1)

        # PE filter
        self.pe_combo = QComboBox()
        self.pe_combo.addItems(["All Listings", "PE Related Only", "Non-PE Related Only"])
        self.pe_combo.currentIndexChanged.connect(self.apply_filters)
        filter_layout.addWidget(QLabel("PE Content:"), 0, 2)
        filter_layout.addWidget(self.pe_combo, 0, 3)

        # Date range
        self.date_from = QDateEdit(calendarPopup=True)
        self.date_to = QDateEdit(calendarPopup=True)
        self.date_from.setDate(QDate(2022, 1, 1))
        self.date_to.setDate(QDate.currentDate())
        self.date_from.dateChanged.connect(self.apply_filters)
        self.date_to.dateChanged.connect(self.apply_filters)

        filter_layout.addWidget(QLabel("Date From:"), 1, 0)
        filter_layout.addWidget(self.date_from, 1, 1)
        filter_layout.addWidget(QLabel("Date To:"), 1, 2)
        filter_layout.addWidget(self.date_to, 1, 3)

        # Search
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
        try:
            self.api_service = api_service
            self.all_listings_data = []

            if self.parent:
                self.parent.add_status("Loading listings...")

            # Get listings from the API service
            listings = api_service.get_saved_listings()

            if not listings:
                if self.parent:
                    self.parent.add_status("No listings found. Please fetch data first.")
                return

            if self.parent:
                self.parent.add_status(f"Found {len(listings)} listings in index.")

            # Process listings
            self.table.setSortingEnabled(False)
            self.table.setRowCount(0)
            listing_count = 0
            error_count = 0

            for key, listing_info in listings.items():
                try:
                    file_path = listing_info["file_path"]
                    if not os.path.exists(file_path):
                        if self.parent:
                            self.parent.add_status(f"Warning: File not found: {file_path}")
                        continue

                    content = api_service.get_listing_content(file_path=file_path)
                    if content == "Listing not found" or not content:
                        if self.parent:
                            self.parent.add_status(f"Warning: Empty content for {file_path}")
                        continue

                    # Extract data (known format from ApiService)
                    lines = content.split("\n")
                    title = next((line.replace("Title:", "").strip() for line in lines if line.startswith("Title:")),
                                 "")
                    date_str = next((line.replace("Date:", "").strip() for line in lines if line.startswith("Date:")),
                                    "")

                    # Get description (known format)
                    desc_idx = content.find("Description:")
                    description = content[desc_idx + len("Description:"):].strip() if desc_idx != -1 else ""

                    # Parse with TextParser
                    parsed = self.parser.parse(title, description, date_str)

                    # Store data
                    listing_data = {
                        "id": listing_info["id"],
                        "date_str": date_str,
                        "date": None,  # Will be set below if parsing succeeds
                        "source": listing_info["source"],
                        "role": parsed["role"],
                        "pe_related": parsed["PE"],
                        "pe_categories": parsed["pe_categories"],
                        "content": content,
                        "title": title,
                        "description": description
                    }

                    # Parse date
                    try:
                        if date_str:
                            listing_data["date"] = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        else:
                            listing_data["date"] = datetime.now()
                    except ValueError:
                        listing_data["date"] = datetime.now()
                    self.all_listings_data.append(listing_data)

                    # Add to table
                    row = self.table.rowCount()
                    self.table.insertRow(row)
                    self.table.setItem(row, 0, QTableWidgetItem(listing_data["id"]))
                    self.table.setItem(row, 1, QTableWidgetItem(str(listing_data["date"])))
                    self.table.setItem(row, 2, QTableWidgetItem(listing_data["source"]))
                    self.table.setItem(row, 3, QTableWidgetItem(listing_data["role"]))
                    self.table.setItem(row, 4, QTableWidgetItem("Yes" if listing_data["pe_related"] else "No"))

                    listing_count += 1

                except Exception as e:
                    error_count += 1
                    if self.parent:
                        self.parent.add_status(f"Error processing listing {key}: {str(e)}")

            if self.parent:
                self.parent.add_status(f"Loaded {listing_count} listings. Errors: {error_count}")

            # Update source filter options
            self.source_combo.clear()
            self.source_combo.addItem("All Sources")
            sources = sorted(set(item["source"] for item in self.all_listings_data))
            self.source_combo.addItems(sources)

            # Update date range
            if self.all_listings_data:
                dates = [item["date"] for item in self.all_listings_data if item["date"]]
                if dates:
                    min_date = min(dates)
                    max_date = max(dates)

                    if isinstance(min_date, datetime):
                        self.date_from.setDate(QDate(min_date.year, min_date.month, min_date.day))
                    if isinstance(max_date, datetime):
                        self.date_to.setDate(QDate(max_date.year, max_date.month, max_date.day))

            self.table.setSortingEnabled(True)
            self.table.sortItems(1, Qt.SortOrder.DescendingOrder)  # Sort by date

            # Apply filters, but make sure we don't hide everything initially
            self.pe_combo.setCurrentIndex(0)  # "All Listings"
            self.apply_filters()

        except Exception as e:
            if self.parent:
                self.parent.add_status(f"Critical error loading data: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to load listings: {str(e)}")

    def apply_filters(self):
        try:
            self.table.setSortingEnabled(False)
            self.table.setRowCount(0)

            # Get filter values
            source_filter = self.source_combo.currentText()
            pe_filter = self.pe_combo.currentText()
            date_from = self.date_from.date().toPyDate()
            date_to = self.date_to.date().toPyDate()
            search_text = self.search_box.text().lower()

            # Apply filters
            filtered_items = []
            for item in self.all_listings_data:
                # Source filter
                if source_filter != "All Sources" and item["source"] != source_filter:
                    continue

                # PE filter
                if pe_filter == "PE Related Only" and not item["pe_related"]:
                    continue
                if pe_filter == "Non-PE Related Only" and item["pe_related"]:
                    continue

                # Date filter
                if item["date"]:
                    item_date = item["date"]
                    if isinstance(item_date, datetime):
                        item_date = item_date.date()
                    if item_date < date_from or item_date > date_to:
                        continue

                # Search filter
                if search_text and search_text not in item["content"].lower():
                    continue

                filtered_items.append(item)

            # Update table
            for item in filtered_items:
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(item["id"]))
                self.table.setItem(row, 1, QTableWidgetItem(str(item["date"])))
                self.table.setItem(row, 2, QTableWidgetItem(item["source"]))
                self.table.setItem(row, 3, QTableWidgetItem(item["role"]))
                self.table.setItem(row, 4, QTableWidgetItem("Yes" if item["pe_related"] else "No"))

            self.table.setSortingEnabled(True)

            if self.parent:
                self.parent.add_status(f"Displaying {self.table.rowCount()} of {len(self.all_listings_data)} listings")

        except Exception as e:
            if self.parent:
                self.parent.add_status(f"Error applying filters: {str(e)}")

    def show_listing_detail(self, row, column):
        try:
            listing_id = self.table.item(row, 0).text()
            source = self.table.item(row, 2).text()

            # Find listing
            for item in self.all_listings_data:
                if item["id"] == listing_id and item["source"] == source:
                    # Format details
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

                    # Highlight PE terms
                    description = item['description']
                    if item['pe_related']:
                        all_terms = []
                        for terms in self.parser.pe_terms.values():
                            all_terms.extend(terms)

                        for term in all_terms:
                            pattern = re.compile(re.escape(term), re.IGNORECASE)
                            description = pattern.sub(f"<span style='background-color: yellow;'>{term}</span>",
                                                      description)

                    html += f"<p>{description.replace(chr(10), '<br>')}</p>"
                    self.details.setHtml(html)
                    break

        except Exception as e:
            if self.parent:
                self.parent.add_status(f"Error showing listing details: {str(e)}")
            self.details.setHtml(f"<p>Error displaying listing details: {str(e)}</p>")

    def export_results(self):
        try:
            filename, _ = QFileDialog.getSaveFileName(self, "Save Results", "", "CSV Files (*.csv)")
            if not filename:
                return

            if not filename.endswith('.csv'):
                filename += '.csv'

            # Get visible rows
            data = []
            for row in range(self.table.rowCount()):
                data.append({
                    'ID': self.table.item(row, 0).text(),
                    'Date': self.table.item(row, 1).text(),
                    'Source': self.table.item(row, 2).text(),
                    'Role': self.table.item(row, 3).text(),
                    'PE_Related': self.table.item(row, 4).text()
                })

            # Save to CSV
            if data:
                df = pd.DataFrame(data)
                df.to_csv(filename, index=False)
                if self.parent:
                    self.parent.add_status(f"Exported {len(data)} records to {filename}")
            else:
                if self.parent:
                    self.parent.add_status("No data to export")

        except Exception as e:
            if self.parent:
                self.parent.add_status(f"Error exporting results: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to export results: {str(e)}")


class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.refresh_browser_btn = None
        self.fetch_worker = None
        self.parser = TextParser()
        self.initUI()

        # Ensure the job_listings directory exists
        os.makedirs("job_listings", exist_ok=True)

        # Initialize API service and load any existing data
        self.api_service = ApiService.ApiService(
            "",  # Empty location
            QDate(2022, 1, 1),  # Default start date
            QDate.currentDate(),  # Default end date
            True,  # Use date
            self.get_selected_sources()  # Default sources
        )

        # Check for existing listings
        listings = self.api_service.get_saved_listings()
        if listings:
            self.add_status(f"Found {len(listings)} existing job listings in database.")
            self.refresh_browser()
        else:
            self.add_status("No existing job listings found. Please fetch data.")

    def initUI(self):
        self.setWindowTitle("Swedish Job Market LLM Analyzer")
        self.setGeometry(100, 50, 1200, 800)

        # Main widget
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

        # Setup tabs
        self.setup_fetch_tab()
        self.setup_analysis_tab()
        self.setup_browser_tab()

        main_layout.addWidget(self.tabs)

        # Status display
        self.statusBox = QTextBrowser()
        self.statusBox.setMaximumHeight(100)
        main_layout.addWidget(QLabel("Status:"))
        main_layout.addWidget(self.statusBox)

        self.central_widget.setLayout(main_layout)

    def setup_fetch_tab(self):
        layout = QVBoxLayout()

        # Parameters
        form_group = QGroupBox("Data Collection Parameters")
        form_layout = QFormLayout()

        # Location field
        self.locationField = QLineEdit()
        self.locationField.setPlaceholderText("e.g., Stockholm, Göteborg, Malmö")
        form_layout.addRow("Location:", self.locationField)

        # Listing count & batch size
        self.listingsCountField = QSpinBox()
        self.listingsCountField.setRange(20, 2000)
        self.listingsCountField.setValue(200)
        form_layout.addRow("Max listings:", self.listingsCountField)

        self.batchSizeField = QSpinBox()
        self.batchSizeField.setRange(10, 50)
        self.batchSizeField.setValue(20)
        form_layout.addRow("Batch size:", self.batchSizeField)

        # Date range
        date_group = QGroupBox("Date Range")
        date_layout = QVBoxLayout()

        self.useDate = QCheckBox("Use date range")
        self.useDate.setChecked(True)

        date_fields = QHBoxLayout()

        self.startDate = QDateEdit(calendarPopup=True)
        self.startDate.setDate(QDate(2022, 1, 1))

        self.endDate = QDateEdit(calendarPopup=True)
        self.endDate.setDate(QDate.currentDate())

        date_fields.addWidget(QLabel("From:"))
        date_fields.addWidget(self.startDate)
        date_fields.addWidget(QLabel("To:"))
        date_fields.addWidget(self.endDate)

        date_layout.addWidget(self.useDate)
        date_layout.addLayout(date_fields)
        date_group.setLayout(date_layout)

        form_layout.addRow(date_group)

        # Sources
        source_group = QGroupBox("Data Sources")
        source_layout = QVBoxLayout()

        self.platsbankenCheck = QCheckBox("Platsbanken")
        self.platsbankenCheck.setChecked(True)
        self.historicalCheck = QCheckBox("Platsbanken Historical Data")
        self.historicalCheck.setChecked(True)

        source_layout.addWidget(self.platsbankenCheck)
        source_layout.addWidget(self.historicalCheck)
        source_group.setLayout(source_layout)

        form_layout.addRow(source_group)
        form_group.setLayout(form_layout)
        layout.addWidget(form_group)

        # Progress bar
        self.progressBar = QProgressBar()
        self.progressBar.setRange(0, 100)
        layout.addWidget(self.progressBar)

        # Buttons
        button_layout = QHBoxLayout()
        self.fetchButton = QPushButton("Fetch Listings")
        self.fetchButton.clicked.connect(self.fetch_listings)
        self.cancelButton = QPushButton("Cancel")
        self.cancelButton.clicked.connect(self.cancel_fetch)
        self.cancelButton.setEnabled(False)

        # Clear Listings button
        self.clearButton = QPushButton("Clear All Listings")
        self.clearButton.clicked.connect(self.clear_listings)

        button_layout.addWidget(self.fetchButton)
        button_layout.addWidget(self.cancelButton)
        button_layout.addWidget(self.clearButton)
        layout.addLayout(button_layout)

        self.fetch_tab.setLayout(layout)

    def setup_analysis_tab(self):
        layout = QVBoxLayout()

        # Visualization options
        graph_group = QGroupBox("Visualization Options")
        graph_layout = QVBoxLayout()

        self.pieBox = QCheckBox("Pie chart - PE vs Non-PE Distribution")
        self.barBox = QCheckBox("Bar chart - PE Distribution by Role")
        self.timeBox = QCheckBox("Time series - PE Trends Over Time")

        self.pieBox.setChecked(True)
        self.barBox.setChecked(True)
        self.timeBox.setChecked(True)

        graph_layout.addWidget(self.pieBox)
        graph_layout.addWidget(self.barBox)
        graph_layout.addWidget(self.timeBox)

        # Date filter
        date_layout = QHBoxLayout()
        self.analysis_start_date = QDateEdit(calendarPopup=True)
        self.analysis_end_date = QDateEdit(calendarPopup=True)

        self.analysis_start_date.setDate(QDate(2022, 1, 1))
        self.analysis_end_date.setDate(QDate.currentDate())

        date_layout.addWidget(QLabel("From:"))
        date_layout.addWidget(self.analysis_start_date)
        date_layout.addWidget(QLabel("To:"))
        date_layout.addWidget(self.analysis_end_date)

        graph_layout.addLayout(date_layout)

        # Export options
        export_layout = QHBoxLayout()
        self.export_graphs_btn = QPushButton("Export Graphs")
        self.export_data_btn = QPushButton("Export Analysis Data")

        self.export_graphs_btn.clicked.connect(self.export_graphs)
        self.export_data_btn.clicked.connect(self.export_analysis_data)

        export_layout.addWidget(self.export_graphs_btn)
        export_layout.addWidget(self.export_data_btn)

        graph_layout.addLayout(export_layout)
        graph_group.setLayout(graph_layout)
        layout.addWidget(graph_group)

        # Analysis button
        analyze_layout = QHBoxLayout()
        self.runAnalysisButton = QPushButton("Run Analysis")
        self.runAnalysisButton.clicked.connect(self.run_analysis)
        analyze_layout.addWidget(self.runAnalysisButton)
        layout.addLayout(analyze_layout)

        # Scroll area for plots
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)

        # Add canvas
        self.canvas = DataAnalysis.DataAnalysis()
        container_layout.addWidget(self.canvas)

        scroll.setWidget(container)
        layout.addWidget(scroll, 1)  # 1 = stretch factor

        self.analysis_tab.setLayout(layout)

    def setup_browser_tab(self):
        layout = QVBoxLayout()

        # Create browser widget
        self.listing_browser = ListingBrowser(self)
        layout.addWidget(self.listing_browser)

        # Refresh button
        self.refresh_browser_btn = QPushButton("Refresh Listings")
        self.refresh_browser_btn.clicked.connect(self.refresh_browser)
        layout.addWidget(self.refresh_browser_btn)

        self.browser_tab.setLayout(layout)

    def add_status(self, message):
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.statusBox.append(f"[{timestamp}] {message}")
        # Scroll to bottom to ensure latest message is visible
        scrollbar = self.statusBox.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        QApplication.processEvents()  # Force UI update

    def get_selected_sources(self):
        sources = []
        if hasattr(self, 'platsbankenCheck') and self.platsbankenCheck.isChecked():
            sources.append("platsbanken")
        if hasattr(self, 'historicalCheck') and self.historicalCheck.isChecked():
            sources.append("platsbanken_historical")
        return sources if sources else None

    def fetch_listings(self):
        try:
            self.fetchButton.setEnabled(False)
            self.cancelButton.setEnabled(True)
            self.progressBar.setValue(0)

            # Get parameters
            location = self.locationField.text()
            max_listings = self.listingsCountField.value()
            batch_size = self.batchSizeField.value()
            sources = self.get_selected_sources()

            if not sources:
                self.add_status("No data sources selected")
                self.fetchButton.setEnabled(True)
                self.cancelButton.setEnabled(False)
                return

            # Create a worker thread
            self.fetch_worker = FetchWorker(
                location,
                self.startDate.date(),
                self.endDate.date(),
                self.useDate.isChecked(),
                max_listings,
                batch_size,
                sources
            )

            # Connect signals
            self.fetch_worker.update_signal.connect(self.add_status)
            self.fetch_worker.progress_signal.connect(self.update_progress)
            self.fetch_worker.finished_signal.connect(self.fetch_completed)
            self.fetch_worker.finished.connect(self.fetch_worker_done)

            # Start fetching
            self.fetch_worker.start()

        except Exception as e:
            self.add_status(f"Error starting fetch: {str(e)}")
            self.fetchButton.setEnabled(True)
            self.cancelButton.setEnabled(False)

    def update_progress(self, current, total):
        percentage = min(int((current / total) * 100), 100)
        self.progressBar.setValue(percentage)

    def fetch_completed(self, saved_paths):
        self.add_status(f"Fetching completed, got {len(saved_paths)} listings")
        # Refresh the browser tab with new data
        self.refresh_browser()
        # Switch to browser tab to show results immediately
        self.tabs.setCurrentIndex(2)

    def fetch_worker_done(self):
        self.fetchButton.setEnabled(True)
        self.cancelButton.setEnabled(False)
        self.fetch_worker = None

    def cancel_fetch(self):
        if self.fetch_worker and self.fetch_worker.isRunning():
            self.fetch_worker.requestInterruption()
            self.add_status("Canceling fetch operation...")

    def clear_listings(self):
        reply = QMessageBox.question(
            self, 'Confirm Clear',
            'Are you sure you want to delete all job listings?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Initialize API service
                api_service = ApiService.ApiService(
                    self.locationField.text(),
                    self.startDate.date(),
                    self.endDate.date(),
                    self.useDate.isChecked(),
                    self.get_selected_sources()
                )

                # Clear all listings
                removed = api_service.clear_listings()
                self.add_status(f"Cleared all job listings from database")

                # Refresh browser tab
                self.refresh_browser()

            except Exception as e:
                self.add_status(f"Error clearing listings: {str(e)}")
                QMessageBox.critical(self, "Error", f"Failed to clear listings: {str(e)}")

    def refresh_browser(self):
        try:
            self.add_status("Refreshing browser view...")

            # Initialize API service
            api_service = ApiService.ApiService(
                self.locationField.text(),
                self.startDate.date(),
                self.endDate.date(),
                self.useDate.isChecked(),
                self.get_selected_sources()
            )

            # Check if the job_listings directory exists and has files
            if not os.path.exists("job_listings"):
                os.makedirs("job_listings", exist_ok=True)
                self.add_status("Created job_listings directory")

            files = [f for f in os.listdir("job_listings") if f.endswith('.txt')]
            if not files:
                self.add_status("No job listing files found. Please fetch data first.")
            else:
                self.add_status(f"Found {len(files)} job listing files")

            # Load data
            self.api_service = api_service
            self.listing_browser.load_data(api_service)

        except Exception as e:
            self.add_status(f"Error refreshing browser: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to refresh listings: {str(e)}")

    def run_analysis(self):
        try:
            self.add_status("Running analysis...")

            # Get options
            graph_types = {
                "pie": self.pieBox.isChecked(),
                "bar": self.barBox.isChecked(),
                "time": self.timeBox.isChecked(),
            }

            start_date = self.analysis_start_date.date().toPyDate()
            end_date = self.analysis_end_date.date().toPyDate()

            # Get API service and listings
            api_service = ApiService.ApiService(
                self.locationField.text(),
                self.startDate.date(),
                self.endDate.date(),
                self.useDate.isChecked(),
                self.get_selected_sources()
            )

            listings = api_service.get_saved_listings()

            if not listings:
                self.add_status("No listings found")
                return

            # Process listings
            analysis_data = []
            error_count = 0

            for key, info in listings.items():
                try:
                    # Check if a file exists
                    if not os.path.exists(info["file_path"]):
                        continue

                    # Get content
                    content = api_service.get_listing_content(file_path=info["file_path"])
                    if not content or content == "Listing not found":
                        continue

                    # Extract data
                    lines = content.split("\n")
                    title = next((line.replace("Title:", "").strip() for line in lines if line.startswith("Title:")),
                                 "")
                    date_str = next((line.replace("Date:", "").strip() for line in lines if line.startswith("Date:")),
                                    "")

                    # Get description
                    desc_idx = content.find("Description:")
                    description = content[desc_idx + len("Description:"):].strip() if desc_idx != -1 else ""

                    # Check date with consistent ISO parsing
                    if date_str:
                        try:
                            listing_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                            # Convert to date for comparison with filter dates
                            if listing_date.date() < start_date or listing_date.date() > end_date:
                                continue
                        except ValueError:
                            pass

                    # Parse
                    parsed = self.parser.parse(title, description, date_str)
                    analysis_data.append(json.dumps(parsed))

                except Exception as e:
                    error_count += 1
                    if error_count < 5:
                        self.add_status(f"Error processing listing {key}: {str(e)}")
                    elif error_count == 5:
                        self.add_status("Too many errors. Suppressing further error messages...")

            # Load data and plot
            if analysis_data:
                self.canvas.load_data(analysis_data, graph_types)
                self.canvas.plot_data()
                self.add_status(f"Analysis complete: {len(analysis_data)} listings processed, {error_count} errors")
            else:
                self.add_status("No data to analyze")

        except Exception as e:
            self.add_status(f"Error running analysis: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to run analysis: {str(e)}")

    def export_graphs(self):
        try:
            directory = QFileDialog.getExistingDirectory(self, "Select Directory to Save Graphs")
            if not directory:
                return

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Create and save individual charts
            if self.canvas.graphtype.get("time", True):
                fig_time, ax_time = plt.subplots(figsize=(10, 6))
                self.canvas._plot_time_series(ax_time)
                time_path = os.path.join(directory, f"time_series_{timestamp}.png")
                fig_time.tight_layout()
                fig_time.savefig(time_path, dpi=300)
                plt.close(fig_time)
                self.add_status(f"Saved time series chart to {time_path}")

            if self.canvas.graphtype.get("bar", True):
                fig_bar, ax_bar = plt.subplots(figsize=(10, 6))
                self.canvas._plot_bar_chart(ax_bar)
                bar_path = os.path.join(directory, f"role_distribution_{timestamp}.png")
                fig_bar.tight_layout()
                fig_bar.savefig(bar_path, dpi=300)
                plt.close(fig_bar)
                self.add_status(f"Saved role distribution chart to {bar_path}")

            if self.canvas.graphtype.get("pie", True):
                fig_pie, ax_pie = plt.subplots(figsize=(10, 6))
                self.canvas._plot_pie_chart(ax_pie)
                pie_path = os.path.join(directory, f"pe_distribution_{timestamp}.png")
                fig_pie.tight_layout()
                fig_pie.savefig(pie_path, dpi=300)
                plt.close(fig_pie)
                self.add_status(f"Saved PE distribution chart to {pie_path}")

            #PE time graph, only in export
            fig_pe_time, ax_pe_time = plt.subplots(figsize=(10, 6))
            self.canvas._plot_pe_time_series(ax_pe_time)
            pe_time_path = os.path.join(directory, f"pe_only_time_series_{timestamp}.png")
            fig_pe_time.tight_layout()
            fig_pe_time.savefig(pe_time_path, dpi=300)
            plt.close(fig_pe_time)
            self.add_status(f"Saved PE-only time series chart to {pe_time_path}")

            # PE role chart, only in export
            bar_pe_path = os.path.join(directory, f"role_distribution_PE_{timestamp}.png")
            fig, ax = plt.subplots(figsize=(8, 6))

            # Sort and plot
            data = [(count, name) for count, name in zip(self.canvas.bar_values[2], self.canvas.bar_pe_names)]
            data.sort(reverse=True)
            counts, names = zip(*data)

            ax.bar(range(len(counts)), counts, color=self.canvas.colors['pe'])
            ax.set_xticks(range(len(counts)))
            ax.set_xticklabels(names, rotation=45, ha='right')
            ax.set_title("SE Roles with highest PE demand")

            plt.tight_layout()
            plt.savefig(bar_pe_path, dpi=300)
            plt.close(fig)
            self.add_status(f"Saved PE roles chart to {bar_pe_path}")

        except Exception as e:
            self.add_status(f"Error exporting graphs: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to export graphs: {str(e)}")

    def export_analysis_data(self):
        try:
            filename, _ = QFileDialog.getSaveFileName(self, "Save Analysis Data", "", "CSV Files (*.csv)")
            if not filename:
                return

            if not filename.endswith('.csv'):
                filename += '.csv'

            # Get API service
            api_service = ApiService.ApiService(
                self.locationField.text(),
                self.startDate.date(),
                self.endDate.date(),
                self.useDate.isChecked(),
                self.get_selected_sources()
            )

            # Get listings
            listings = api_service.get_saved_listings()

            # Process listings
            data = []
            error_count = 0

            for key, info in listings.items():
                try:
                    # Check if file exists
                    if not os.path.exists(info["file_path"]):
                        continue

                    # Get content
                    content = api_service.get_listing_content(file_path=info["file_path"])
                    if not content or content == "Listing not found":
                        continue

                    # Extract data
                    lines = content.split("\n")
                    title = next((line.replace("Title:", "").strip() for line in lines if line.startswith("Title:")),
                                 "")
                    date_str = next((line.replace("Date:", "").strip() for line in lines if line.startswith("Date:")),
                                    "")

                    # Get description
                    desc_idx = content.find("Description:")
                    description = content[desc_idx + len("Description:"):].strip() if desc_idx != -1 else ""

                    # Parse with TextParser
                    parsed = self.parser.parse(title, description, date_str)

                    # Add to dataset
                    row = {
                        'ID': info["id"],
                        'Source': info["source"],
                        'Date': date_str,
                        'Role': parsed["role"],
                        'PE_Related': 'Yes' if parsed["PE"] else 'No'
                    }

                    # Add categories
                    for category, present in parsed["pe_categories"].items():
                        row[f'Category_{category}'] = 'Yes' if present else 'No'

                    data.append(row)

                except Exception as e:
                    error_count += 1
                    if error_count < 5:  # Limit error messages
                        self.add_status(f"Error processing listing {key}: {str(e)}")
                    elif error_count == 5:
                        self.add_status("Too many errors. Suppressing further error messages...")

            # Save to CSV
            if data:
                df = pd.DataFrame(data)
                df.to_csv(filename, index=False)
                self.add_status(f"Exported {len(data)} records to {filename}")
            else:
                self.add_status("No data to export")

        except Exception as e:
            self.add_status(f"Error exporting analysis data: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to export analysis data: {str(e)}")

    def resizeEvent(self, event):
        if hasattr(self, 'canvas'):
            self.canvas.resize(self.analysis_tab.size())
        super().resizeEvent(event)


if __name__ == '__main__':
    app = QApplication([])
    window = Main()
    window.show()
    sys.exit(app.exec())