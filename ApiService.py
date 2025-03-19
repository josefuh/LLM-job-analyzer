import grequests
import os

from PyQt6.QtCore import Qt, QDate
from dotenv import load_dotenv
import urllib.parse


class ApiService:
    """ Class used to get job postings from API:s

    Parameters
    ----------
    location: str, optional
        specific location to get job postings from
    start_date: QDate
        starting date specifying the lower bound for the date that
        a job listing was posted
    end_date: QDate
        specifying the upper bound for the date that a job listing
        was posted
    use_date: bool
        flag for whether to use the specified time frame or use the
        default being: 1/1-25 to the current date
    """

    def __init__(self, location, start_date, end_date, use_date):
        load_dotenv()

        self.location = location

        query = "q=utvecklare%20" + location
        if start_date.daysTo(end_date) > 0 and use_date is True:
            self.start_date = urllib.parse.quote(start_date.toString(format=Qt.DateFormat.ISODateWithMs) + "T00:00:00")
            self.end_date = urllib.parse.quote(end_date.toString(format=Qt.DateFormat.ISODateWithMs) + "T00:00:00")
            query += "&published-before=" + self.end_date + "&published-after=" + self.start_date
        else:
            self.start_date = urllib.parse.quote(
                QDate(2025, 1, 1).toString(format=Qt.DateFormat.ISODateWithMs) + "T00:00:00")
            self.end_date = urllib.parse.quote(
                QDate().currentDate().toString(format=Qt.DateFormat.ISODateWithMs) + "T00:00:00")

        self.sources = {
            "https://indeed12.p.rapidapi.com/jobs/search",  # indeed
            "https://jobsearch.api.jobtechdev.se/search?" + query + "&limit=20",  # platsbanken
            #"https://jsearch.p.rapidapi.com/search"                            # jSearch
            "https://job-posting-feed-api.p.rapidapi.com/active-ats-meili"  # job posting
        }
        api_key = os.environ.get("RAPID_API_KEY")
        self.headers = [
            {"x-rapidapi-key": api_key,
             "x-rapidapi-host": "indeed12.p.rapidapi.com"},
            {},
            #{"x-rapidapi-key": api_key,             "x-rapidapi-host": "jsearch.p.rapidapi.com"}
            {"x-rapidapi-key": api_key,
             "x-rapidapi-host": "job-posting-feed-api.p.rapidapi.com"}
        ]

    def load(self):
        """ Method for making HTTP requests to each API

        :return: Array of the content of each HTTP response
        """
        querystring = [
            {"query": "software developer"},
            {},
            #{"query": ("software developer "+self.location), "date_posted":"all", "fromage":14}
            {"search": "\"software developer\"", "title_search": "false", "description_type": "html"}
        ]
        if self.location != "":
            querystring[0].update({"location": self.location})
            querystring[2].update({"location_filter": self.location})

        reqs = [grequests.get(url, headers=h, params=q) for (url, h, q) in zip(self.sources, self.headers, querystring)]
        response = grequests.imap(reqs, size=3)

        return [r.content for r in response]
