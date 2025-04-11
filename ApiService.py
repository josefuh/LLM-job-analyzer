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
    """ Class used to get job postings from APIs and save them locally
    with a focus on Swedish job market.

    Parameters
    ----------
    location: str, optional
        specific location to get job postings from (e.g., Stockholm, Göteborg)
    start_date: QDate
        starting date specifying the lower bound for listings
    end_date: QDate
        specifying the upper bound for listings
    use_date: bool
        flag for whether to use the specified time frame
    """

    def __init__(self, location, start_date, end_date, use_date,
                 sources=None, enable_international=False):
        load_dotenv()

        self.location = location
        self.listings_dir = "job_listings"
        self.index_file = os.path.join(self.listings_dir, "index.json")
        self.listings_index = {}
        self.enable_international = enable_international

        # Ensure the listings directory exists
        os.makedirs(self.listings_dir, exist_ok=True)

        # Load the listings index if it exists
        if os.path.exists(self.index_file):
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    self.listings_index = json.load(f)
            except Exception as e:
                print(f"Error loading listings index: {e}")

        # Set up date parameters
        self._setup_date_parameters(start_date, end_date, use_date)

        # Configure API sources
        self.sources = self._configure_sources(sources)

        # Update location parameters if specified
        if self.location:
            self._update_location_parameters()

    def _setup_date_parameters(self, start_date, end_date, use_date):
        """Set up date parameters for API queries"""
        # Regular date parameters
        if start_date.daysTo(end_date) > 0 and use_date is True:
            self.start_date = urllib.parse.quote(start_date.toString(format=Qt.DateFormat.ISODateWithMs) + "T00:00:00")
            self.end_date = urllib.parse.quote(end_date.toString(format=Qt.DateFormat.ISODateWithMs) + "T00:00:00")

            # Store Python date objects for historical queries
            self.start_date_obj = start_date.toPyDate()
            self.end_date_obj = end_date.toPyDate()
        else:
            # Default to Jan 2022 to present (based on project requirements)
            default_start = QDate(2022, 1, 1)
            self.start_date = urllib.parse.quote(
                default_start.toString(format=Qt.DateFormat.ISODateWithMs) + "T00:00:00")
            self.end_date = urllib.parse.quote(
                QDate().currentDate().toString(format=Qt.DateFormat.ISODateWithMs) + "T00:00:00")

            # Store Python date objects
            self.start_date_obj = default_start.toPyDate()
            self.end_date_obj = QDate().currentDate().toPyDate()

    def _configure_sources(self, sources=None):
        """Configure the API sources with appropriate parameters"""
        # Default limit for API queries
        limit = 20

        # Build a more inclusive query for software engineering roles
        # This will search for multiple common software roles instead of just "utvecklare"
        query_terms = [
            "utvecklare", "programmerare", "mjukvaruutvecklare", "systemutvecklare",
            "software", "developer", "engineer", "programmer", "arkitekt", "architect"
        ]

        # Pick two random terms to create variation in results
        import random
        selected_terms = random.sample(query_terms, 2)
        query_string = "%20OR%20".join(selected_terms)

        # Add location if specified
        location_query = f"q={query_string}{'%20' + self.location if self.location else ''}"

        # Build query parameters for date range
        date_params = f"&published-before={self.end_date}&published-after={self.start_date}"

        # Dictionary of all possible sources
        all_sources = {
            # Swedish sources (primary focus)
            "platsbanken": {
                "enabled": True,
                "priority": 1,
                "url": f"https://jobsearch.api.jobtechdev.se/search?{location_query}&limit={limit}{date_params}",
                "headers": {},
                "params": {}
            },
            "platsbanken_historical": {
                "enabled": True,
                "priority": 2,
                "url": f"https://historical.api.jobtechdev.se/search?q={query_string}&request-timeout=300&limit={limit}&historical-from={self.start_date}&historical-to={self.end_date}",
                "headers": {},
                "params": {}
            },

            # International sources (optional)
            "indeed": {
                "enabled": self.enable_international,
                "priority": 3,
                "url": "https://indeed12.p.rapidapi.com/jobs/search",
                "headers": {
                    "x-rapidapi-key": os.environ.get("RAPID_API_KEY"),
                    "x-rapidapi-host": "indeed12.p.rapidapi.com"
                },
                "params": {
                    "query": "software engineer sweden",
                    "language": "sv",
                    "country": "se"
                }
            },
            "job_posting_feed": {
                "enabled": self.enable_international,
                "priority": 4,
                "url": "https://job-posting-feed-api.p.rapidapi.com/active-ats-meili",
                "headers": {
                    "x-rapidapi-key": os.environ.get("RAPID_API_KEY"),
                    "x-rapidapi-host": "job-posting-feed-api.p.rapidapi.com"
                },
                "params": {
                    "search": "\"software engineer\" sweden",
                    "title_search": "false",
                    "description_type": "html",
                    "country": "sweden"
                }
            }
        }

        # Override default sources if specified
        if sources is not None:
            for source_name, enabled in sources.items():
                if source_name in all_sources:
                    all_sources[source_name]["enabled"] = enabled

        # Filter to only enabled sources
        enabled_sources = {k: v for k, v in all_sources.items() if v["enabled"]}

        # Sort by priority
        return dict(sorted(enabled_sources.items(), key=lambda x: x[1]["priority"]))

    def _update_location_parameters(self):
        """Update location parameters in API sources"""
        if "indeed" in self.sources:
            self.sources["indeed"]["params"].update({
                "location": self.location,
                "query": f"software engineer {self.location} sweden"
            })

        if "job_posting_feed" in self.sources:
            self.sources["job_posting_feed"]["params"].update({
                "location_filter": f"{self.location}, sweden",
                "search": f"\"software engineer\" {self.location} sweden"
            })

        if "platsbanken" in self.sources:
            # Extract the base query from existing URL
            current_url = self.sources["platsbanken"]["url"]
            start_q = current_url.find("q=") + 2
            end_q = current_url.find("&", start_q) if "&" in current_url[start_q:] else len(current_url)
            base_query = current_url[start_q:end_q]

            # Add location to the query if specified
            if self.location:
                new_query = f"{base_query}%20{urllib.parse.quote(self.location)}"
                self.sources["platsbanken"]["url"] = current_url.replace(
                    f"q={base_query}", f"q={new_query}")

        if "platsbanken_historical" in self.sources:
            # Extract the base query from existing URL
            current_url = self.sources["platsbanken_historical"]["url"]
            start_q = current_url.find("q=") + 2
            end_q = current_url.find("&", start_q) if "&" in current_url[start_q:] else len(current_url)
            base_query = current_url[start_q:end_q]

            # Add location to the query if specified
            if self.location:
                new_query = f"{base_query}%20{urllib.parse.quote(self.location)}"
                self.sources["platsbanken_historical"]["url"] = current_url.replace(
                    f"q={base_query}", f"q={new_query}")

    def load(self, batch_offset=0):
        """Method for making HTTP requests to each API and save listings

        Args:
            batch_offset (int): Offset for pagination in batch fetching

        Returns:
            list: Saved job listings file paths
        """
        # Prepare requests
        reqs = []
        source_names = []

        # Add offset to URLs if applicable
        for source_name, config in self.sources.items():
            url = config["url"]

            # Add offset for pagination if supported
            if batch_offset > 0:
                if source_name in ["platsbanken", "platsbanken_historical"]:
                    if "offset=" in url:
                        url = url.replace(f"offset={url.split('offset=')[1].split('&')[0]}", f"offset={batch_offset}")
                    else:
                        url += f"&offset={batch_offset}"

            # Create the request
            reqs.append(grequests.get(
                url,
                headers=config["headers"],
                params=config["params"]
            ))
            source_names.append(source_name)

        # Execute requests concurrently
        responses = grequests.imap(reqs, size=len(reqs))

        # Process responses and save listings
        saved_paths = []
        for source_name, response in zip(source_names, responses):
            if response and response.status_code == 200:
                # Process and save listings from this response
                listing_paths = self._process_and_save_listings(source_name, response.content)
                saved_paths.extend(listing_paths)

                # Add a small delay to avoid overloading APIs
                time.sleep(random.uniform(0.5, 1.0))

        # Save the updated listings index
        self._save_listings_index()

        return saved_paths

    def load_historical_range(self, max_listings=500):
        """Load historical data in smaller segments to avoid timeout issues

        Args:
            max_listings (int): Maximum number of listings to fetch

        Returns:
            list: Saved job listings file paths
        """
        if "platsbanken_historical" not in self.sources:
            return []

        saved_paths = []

        # Calculate number of months between start and end date
        start_date = self.start_date_obj
        end_date = self.end_date_obj

        # Break into 3-month segments
        current_start = start_date
        segment_count = 0

        while current_start < end_date and len(saved_paths) < max_listings:
            # Calculate the end of this segment (3 months or end_date, whichever is sooner)
            segment_end = min(
                end_date,
                datetime(
                    current_start.year + ((current_start.month + 2) // 12),
                    ((current_start.month + 2) % 12) + 1,
                    1
                ).date() - timedelta(days=1)
            )

            # Format dates for API
            from_date = urllib.parse.quote(current_start.strftime("%Y-%m-%d") + "T00:00:00")
            to_date = urllib.parse.quote(segment_end.strftime("%Y-%m-%d") + "T23:59:59")

            # Update the URL with the segment dates
            original_url = self.sources["platsbanken_historical"]["url"]
            segment_url = original_url.replace(
                f"historical-from={self.start_date}&historical-to={self.end_date}",
                f"historical-from={from_date}&historical-to={to_date}"
            )

            # Save the original URL
            orig_url = self.sources["platsbanken_historical"]["url"]
            self.sources["platsbanken_historical"]["url"] = segment_url

            try:
                # Fetch this segment
                print(f"Fetching historical segment {segment_count + 1}: {current_start} to {segment_end}")
                segment_paths = self.load()
                saved_paths.extend(segment_paths)

                # Stop if we reached the limit
                if len(saved_paths) >= max_listings:
                    break

            except Exception as e:
                print(f"Error fetching segment {segment_count + 1}: {e}")

            finally:
                # Restore the original URL
                self.sources["platsbanken_historical"]["url"] = orig_url

            # Move to next segment
            current_start = segment_end + timedelta(days=1)
            segment_count += 1

            # Small delay between segments
            time.sleep(random.uniform(1.0, 2.0))

        return saved_paths

    def _process_and_save_listings(self, source_name, response_content):
        """Process the API response and save unique listings to files

        Args:
            source_name (str): Name of the source API
            response_content (bytes): API response content

        Returns:
            list: Paths to the saved listing files
        """
        saved_paths = []

        try:
            # Parse the response content
            data = json.loads(response_content)

            # Extract listings based on the source format
            listings = []
            if source_name == "indeed":
                listings = data.get("hits", [])
            elif source_name == "platsbanken" or source_name == "platsbanken_historical":
                listings = data.get("hits", [])
            elif source_name == "job_posting_feed":
                listings = data.get("jobs", [])

            # Save each listing to a file if it's not a duplicate
            for listing in listings:
                listing_id, listing_date, listing_body, metadata = self._extract_listing_info(source_name, listing)

                if listing_id and not self._is_duplicate(source_name, listing_id):
                    # Create a unique filename
                    date_str = listing_date.strftime("%Y%m%d") if listing_date else "unknown_date"
                    filename = f"{source_name}_{date_str}_{listing_id}.txt"
                    file_path = os.path.join(self.listings_dir, filename)

                    # Save the listing
                    with open(file_path, 'w', encoding='utf-8') as f:
                        # Add metadata at the top
                        f.write(f"Source: {source_name}\n")
                        f.write(f"Date: {listing_date}\n")
                        f.write(f"ID: {listing_id}\n")

                        # Add additional metadata
                        for key, value in metadata.items():
                            f.write(f"{key}: {value}\n")

                        f.write("-" * 50 + "\n\n")
                        f.write(listing_body)

                    # Add to the index
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
        """Extract ID, date, body, and metadata from a listing based on its source

        Args:
            source_name (str): Name of the source API
            listing (dict): The listing data

        Returns:
            tuple: (listing_id, listing_date, listing_body, metadata)
        """
        listing_id = None
        listing_date = None
        listing_body = ""
        metadata = {}

        try:
            if source_name == "indeed":
                listing_id = listing.get("jobkey")
                date_str = listing.get("formattedRelativeTime", "")

                # Try to parse the date or use current date
                listing_date = datetime.now()  # Fallback to current date

                # Extract metadata
                metadata = {
                    "Company": listing.get("company", "No Company"),
                    "Location": listing.get("formattedLocation", "No Location"),
                    "Country": "Sweden" if "sweden" in str(listing.get("formattedLocation", "")).lower() else "Unknown"
                }

                listing_body = (
                    f"Title: {listing.get('title', 'No Title')}\n"
                    f"Company: {metadata['Company']}\n"
                    f"Location: {metadata['Location']}\n\n"
                    f"Description:\n{listing.get('snippet', 'No Description')}"
                )

            elif source_name == "platsbanken" or source_name == "platsbanken_historical":
                listing_id = listing.get("id")

                # Parse date from the published timestamp
                date_str = listing.get("publication_date")
                if date_str:
                    try:
                        listing_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    except:
                        listing_date = datetime.now()

                # Extract workplace locations
                workplace_addresses = listing.get("workplace_addresses", [])
                locations = ', '.join(
                    [loc.get("municipality", "") for loc in workplace_addresses if loc.get("municipality")])

                # Extract occupation
                occupation = listing.get("occupation", {}).get("label", "")

                # Extract metadata
                metadata = {
                    "Company": listing.get("employer", {}).get("name", "No Company"),
                    "Location": locations,
                    "Occupation": occupation,
                    "Country": "Sweden"
                }

                # Extract application details
                application_details = listing.get("application_details", {})
                if application_details:
                    metadata["Email"] = application_details.get("email", "")
                    metadata["URL"] = application_details.get("url", "")

                # Create listing body
                listing_body = (
                    f"Title: {listing.get('headline', 'No Title')}\n"
                    f"Company: {metadata['Company']}\n"
                    f"Location: {metadata['Location']}\n"
                    f"Occupation: {metadata['Occupation']}\n\n"
                    f"Description:\n{listing.get('description', {}).get('text', 'No Description')}"
                )

            elif source_name == "job_posting_feed":
                listing_id = listing.get("id")
                date_str = listing.get("posted_at")
                if date_str:
                    try:
                        listing_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    except:
                        listing_date = datetime.now()

                # Extract metadata
                metadata = {
                    "Company": listing.get("company", {}).get("name", "No Company"),
                    "Location": listing.get("location", {}).get("name", "No Location"),
                    "Country": "Sweden" if "sweden" in str(listing.get("location", {})).lower() else "Unknown"
                }

                listing_body = (
                    f"Title: {listing.get('title', 'No Title')}\n"
                    f"Company: {metadata['Company']}\n"
                    f"Location: {metadata['Location']}\n\n"
                    f"Description:\n{listing.get('description', 'No Description')}"
                )
        except Exception as e:
            print(f"Error extracting info from {source_name} listing: {e}")

        return listing_id, listing_date, listing_body, metadata

    def _is_duplicate(self, source_name, listing_id):
        """Check if a listing with the given ID already exists

        Args:
            source_name (str): Name of the source API
            listing_id (str): The ID of the listing to check

        Returns:
            bool: True if the listing already exists, False otherwise
        """
        # Check if the listing exists in our index
        return f"{source_name}_{listing_id}" in self.listings_index

    def _save_listings_index(self):
        """Save the listings index to a file"""
        try:
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(self.listings_index, f, indent=2)
        except Exception as e:
            print(f"Error saving listings index: {e}")

    def get_saved_listings(self, filter_params=None):
        """Get saved job listings, optionally filtered

        Args:
            filter_params (dict, optional): Filtering parameters
                - date_from: Start date
                - date_to: End date
                - sources: List of sources to include
                - location: Location filter

        Returns:
            dict: Information about all saved job listings
        """
        if not filter_params:
            return self.listings_index

        # Apply filters
        filtered_listings = {}
        for key, listing in self.listings_index.items():
            # Check source filter
            if filter_params.get("sources") and listing["source"] not in filter_params["sources"]:
                continue

            # Check date filter
            if filter_params.get("date_from") or filter_params.get("date_to"):
                try:
                    listing_date = datetime.strptime(listing["date"], "%Y%m%d").date()

                    if filter_params.get("date_from") and listing_date < filter_params["date_from"]:
                        continue

                    if filter_params.get("date_to") and listing_date > filter_params["date_to"]:
                        continue
                except:
                    # If we can't parse the date, include it anyway
                    pass

            # Check location filter
            if filter_params.get("location") and listing.get("metadata", {}).get("Location"):
                if filter_params["location"].lower() not in listing["metadata"]["Location"].lower():
                    continue

            # Include this listing
            filtered_listings[key] = listing

        return filtered_listings

    def get_listing_content(self, file_path=None, listing_id=None, source_name=None):
        """Get the content of a saved job listing

        Args:
            file_path (str, optional): Path to the job listing file
            listing_id (str, optional): ID of the listing to retrieve
            source_name (str, optional): Source name when using listing_id

        Returns:
            str: Content of the job listing
        """
        try:
            # If a file path is provided, use it directly
            if file_path:
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        return f.read()
                else:
                    return f"File not found: {file_path}"

            # If listing ID and source name are provided, look up the file path
            elif listing_id and source_name:
                index_key = f"{source_name}_{listing_id}"
                if index_key in self.listings_index:
                    file_path = self.listings_index[index_key]["file_path"]
                    if os.path.exists(file_path):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            return f.read()
                    else:
                        return f"File not found: {file_path}"
                else:
                    return f"Listing {listing_id} from {source_name} not found"

            else:
                return "Please provide either a file path or a listing ID and source name"

        except Exception as e:
            print(f"Error reading listing: {e}")
            return f"Error reading listing: {e}"

    def clear_listings(self, filter_params=None):
        """Clear saved listings, optionally based on filters

        Args:
            filter_params (dict, optional): Filtering parameters
                - date_from: Start date
                - date_to: End date
                - sources: List of sources to include
                - location: Location filter

        Returns:
            int: Number of listings removed
        """
        if not filter_params:
            # Clear all listings
            if os.path.exists(self.listings_dir):
                shutil.rmtree(self.listings_dir)
                os.makedirs(self.listings_dir)
            self.listings_index = {}
            self._save_listings_index()
            return len(self.listings_index)

        # Get listings to remove
        to_remove = self.get_saved_listings(filter_params)
        removed_count = 0

        # Remove each listing
        for key, listing in to_remove.items():
            file_path = listing["file_path"]
            if os.path.exists(file_path):
                os.remove(file_path)
            if key in self.listings_index:
                del self.listings_index[key]
                removed_count += 1

        # Save updated index
        self._save_listings_index()
        return removed_count

    def export_listings(self, output_path, filter_params=None):
        """Export listings to a directory

        Args:
            output_path (str): Directory to export to
            filter_params (dict, optional): Filtering parameters

        Returns:
            int: Number of listings exported
        """
        # Create the output directory if it doesn't exist
        os.makedirs(output_path, exist_ok=True)

        # Get listings to export
        if filter_params:
            listings = self.get_saved_listings(filter_params)
        else:
            listings = self.listings_index

        # Export each listing
        exported_count = 0
        for key, listing in listings.items():
            src_path = listing["file_path"]
            if os.path.exists(src_path):
                # Create destination path
                dest_filename = os.path.basename(src_path)
                dest_path = os.path.join(output_path, dest_filename)

                # Copy the file
                shutil.copy2(src_path, dest_path)
                exported_count += 1

        return exported_count