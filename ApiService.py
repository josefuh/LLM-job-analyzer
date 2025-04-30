import grequests
import os
import json
import shutil
from datetime import datetime, timedelta
from PyQt6.QtCore import Qt, QDate
from dotenv import load_dotenv
import urllib.parse
import time
import random


class ApiService:
    """ Class for fetching job postings from Swedish job market APIs """

    def __init__(self, location, start_date, end_date, use_date, sources=None):
        load_dotenv()
        self.location = location
        self.listings_dir = "job_listings"
        self.index_file = os.path.join(self.listings_dir, "index.json")
        self.listings_index = {}

        os.makedirs(self.listings_dir, exist_ok=True)

        # Load the existing index if available
        if os.path.exists(self.index_file):
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    self.listings_index = json.load(f)
                # Verify index entries point to existing files
                self.listings_index = {k: v for k, v in self.listings_index.items()
                                       if os.path.exists(v["file_path"])}
            except Exception as e:
                print(f"Error loading index: {e}. Creating new index...")
                self.listings_index = {}

        # Set up date parameters
        self._setup_date_parameters(start_date, end_date, use_date)

        # Configure API sources
        self.sources = self._configure_sources(sources)

        # Add location filtering if specified
        if self.location:
            self._update_location_parameters()

    def _setup_date_parameters(self, start_date, end_date, use_date):
        """Set up date parameters for API queries"""
        if start_date.daysTo(end_date) > 0 and use_date is True:
            # Store dates without URL encoding
            self.start_date = start_date.toString("yyyy-MM-dd") + "T00:00:00"
            self.end_date = end_date.toString("yyyy-MM-dd") + "T23:59:59"

            # Store Python date objects for comparison
            self.start_date_obj = start_date.toPyDate()
            self.end_date_obj = end_date.toPyDate()
        else:
            # Default to Jan 2022 to present
            default_start = QDate(2022, 1, 1)
            self.start_date = default_start.toString("yyyy-MM-dd") + "T00:00:00"
            self.end_date = QDate().currentDate().toString("yyyy-MM-dd") + "T23:59:59"
            self.start_date_obj = default_start.toPyDate()
            self.end_date_obj = QDate().currentDate().toPyDate()

    def _configure_sources(self, sources=None):
        """Configure API endpoints"""
        limit = 20

        # Platsbanken (current job listings)
        platsbanken_url = "https://jobsearch.api.jobtechdev.se/search?"
        platsbanken_params = {
            'occupation-field': 'apaJ_2ja_LuF',
            'limit': limit,
            'published-before': self.end_date,
            'published-after': self.start_date
        }

        # Historical API
        historical_url = "https://historical.api.jobtechdev.se/search?"
        historical_params = {
            'occupation-field': 'apaJ_2ja_LuF',
            'limit': limit,
            'request-timeout': 300,
            'historical-from': self.start_date,
            'historical-to': self.end_date
        }

        all_sources = {
            "platsbanken": {
                "enabled": True,
                "priority": 1,
                "url": platsbanken_url + urllib.parse.urlencode(platsbanken_params),
                "headers": {},
                "params": {}
            },
            "platsbanken_historical": {
                "enabled": True,
                "priority": 2,
                "url": historical_url + urllib.parse.urlencode(historical_params),
                "headers": {},
                "params": {}
            },
        }

        if isinstance(sources, list):
            return {k: v for k, v in all_sources.items() if k in sources}
        else:
            return all_sources

    def _update_location_parameters(self):
        """Add location filtering to API endpoints"""
        if self.location:
            location_encoded = urllib.parse.quote(self.location)

            # Update platsbanken sources with municipality parameter
            for source_name in ["platsbanken", "platsbanken_historical"]:
                if source_name in self.sources:
                    current_url = self.sources[source_name]["url"]
                    if "municipality=" not in current_url:
                        self.sources[source_name]["url"] = f"{current_url}&municipality={location_encoded}"

    def load(self, batch_offset=0):
        """Fetch job listings from configured API sources"""
        reqs = []
        source_names = []

        # Prepare requests
        for source_name, config in self.sources.items():
            url = config["url"]

            if batch_offset > 0 and source_name in ["platsbanken", "platsbanken_historical"]:
                if "offset=" in url:
                    url = url.replace(f"offset={url.split('offset=')[1].split('&')[0]}", f"offset={batch_offset}")
                else:
                    url += f"&offset={batch_offset}"

            print(f"DEBUG: Making request to {source_name} API: {url}")

            reqs.append(grequests.get(url, headers=config["headers"], params=config["params"]))
            source_names.append(source_name)

        responses = grequests.imap(reqs, size=len(reqs))

        saved_paths = []
        for source_name, response in zip(source_names, responses):
            if response and response.status_code == 200:
                print(f"DEBUG: Got successful response from {source_name} API")
                print(f"DEBUG: First 100 chars of response: {response.content[:100]}")

                listing_paths = self._process_and_save_listings(source_name, response.content)
                saved_paths.extend(listing_paths)
                print(f"DEBUG: Saved {len(listing_paths)} listings from {source_name}")

                time.sleep(random.uniform(0.5, 1.0))  # Small delay between requests
            else:
                status = response.status_code if response else "No response"
                error = response.text if response and hasattr(response, 'text') else "Unknown error"
                print(f"DEBUG: Error response from {source_name}: Status {status}, Error: {error[:200]}")

        self._save_listings_index()
        return saved_paths

    def _process_and_save_listings(self, source_name, response_content):
        """Process API response and save listings"""
        saved_paths = []

        try:
            data = json.loads(response_content)
            listings = data.get("hits", [])

            for listing in listings:
                listing_id, listing_date, listing_body, metadata = self._extract_listing_info(source_name, listing)

                # Save only if new listing
                if listing_id and not self._is_duplicate(source_name, listing_id):
                    date_str = listing_date.strftime("%Y%m%d") if listing_date else "unknown_date"
                    filename = f"{source_name}_{date_str}_{listing_id}.txt"
                    file_path = os.path.join(self.listings_dir, filename)

                    # Write listing to the file
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(f"Source: {source_name}\n")
                        f.write(f"Date: {listing_date}\n")
                        f.write(f"ID: {listing_id}\n")

                        for key, value in metadata.items():
                            f.write(f"{key}: {value}\n")

                        f.write("-" * 50 + "\n\n")
                        f.write(listing_body)

                    # Update index
                    self.listings_index[f"{source_name}_{listing_id}"] = {
                        "file_path": file_path,
                        "date": date_str,
                        "source": source_name,
                        "id": listing_id,
                        "metadata": metadata
                    }

                    saved_paths.append(file_path)
        except Exception as e:
            print(f"Error processing {source_name} response: {e}")

        return saved_paths

    def _extract_listing_info(self, source_name, listing):
        """Extract key information from a job listing"""
        try:
            if source_name in ["platsbanken", "platsbanken_historical"]:
                # Get basic info
                listing_id = listing.get("id")

                # Parse date
                date_str = listing.get("publication_date")

                if date_str:
                    try:
                        listing_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    except:
                        listing_date = datetime.now()
                else:
                    listing_date = datetime.now()

                # Get occupation
                occupation = listing.get("occupation", {}).get("label", "")

                # Create metadata
                metadata = {
                    "Company": listing.get("employer", {}).get("name", "No Company"),
                    "Occupation": occupation,
                    "Country": "Sweden"
                }

                # Add application details if available
                application_details = listing.get("application_details", {})
                if application_details:
                    metadata["Email"] = application_details.get("email", "")
                    metadata["URL"] = application_details.get("url", "")

                # Format listing body
                listing_body = (
                    f"Title: {listing.get('headline', 'No Title')}\n"
                    f"Company: {metadata['Company']}\n"
                    f"Occupation: {metadata['Occupation']}\n\n"
                    f"Description:\n{listing.get('description', {}).get('text', 'No Description')}"
                )

                return listing_id, listing_date, listing_body, metadata

            else:
                return None, None, "", {}

        except Exception as e:
            print(f"Error extracting info from {source_name} listing: {e}")
            return None, None, "", {}

    def _is_duplicate(self, source_name, listing_id):
        """Check if a listing already exists"""
        return f"{source_name}_{listing_id}" in self.listings_index

    def _save_listings_index(self):
        """Save the listing index to a file"""
        try:
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(self.listings_index, f, indent=2)
        except Exception as e:
            print(f"Error saving listings index: {e}")

    def get_saved_listings(self, filter_params=None):
        """Get saved listings, optionally filtered"""
        if not filter_params:
            return self.listings_index

        filtered_listings = {}
        for key, listing in self.listings_index.items():
            # Filter by source if specified
            if filter_params.get("sources") and listing["source"] not in filter_params["sources"]:
                continue

            # Filter by date range if specified
            if filter_params.get("date_from") or filter_params.get("date_to"):
                try:
                    listing_date = datetime.strptime(listing["date"], "%Y%m%d").date()
                    if filter_params.get("date_from") and listing_date < filter_params["date_from"]:
                        continue
                    if filter_params.get("date_to") and listing_date > filter_params["date_to"]:
                        continue
                except:
                    pass

            # Filter by location if specified
            if filter_params.get("location") and listing.get("metadata", {}).get("Location"):
                if filter_params["location"].lower() not in listing["metadata"]["Location"].lower():
                    continue

            filtered_listings[key] = listing

        return filtered_listings

    def get_listing_content(self, file_path=None, listing_id=None, source_name=None):
        """Get the content of a specific saved listing"""
        try:
            if file_path and os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            elif listing_id and source_name:
                index_key = f"{source_name}_{listing_id}"
                if index_key in self.listings_index:
                    file_path = self.listings_index[index_key]["file_path"]
                    if os.path.exists(file_path):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            return f.read()

            return "Listing not found"
        except Exception as e:
            return f"Error reading listing: {e}"

    def clear_listings(self, filter_params=None):
        """Clear all or filtered listings"""
        if not filter_params:
            # Clear all listings
            if os.path.exists(self.listings_dir):
                shutil.rmtree(self.listings_dir)
                os.makedirs(self.listings_dir)
            self.listings_index = {}
            self._save_listings_index()
            return 0

        # Clear filtered listings
        to_remove = self.get_saved_listings(filter_params)
        removed_count = 0

        for key, listing in to_remove.items():
            file_path = listing["file_path"]
            if os.path.exists(file_path):
                os.remove(file_path)
            if key in self.listings_index:
                del self.listings_index[key]
                removed_count += 1

        self._save_listings_index()
        return removed_count