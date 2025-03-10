import grequests
import os
from dotenv import load_dotenv

class ApiService:
    def __init__(self):
        load_dotenv()

        self.sources = {
            "https://indeed12.p.rapidapi.com/jobs/search",  # indeed
            "https://jobsearch.api.jobtechdev.se/search?q=utvecklare",   # platsbanken
            "https://jsearch.p.rapidapi.com/search"         # jSearch
        }
        api_key = os.environ.get("RAPID_API_KEY")
        self.headers = [
            {"x-rapidapi-key": api_key,
            "x-rapidapi-host": "indeed12.p.rapidapi.com"},
            {},
            {"x-rapidapi-key": api_key,
             "x-rapidapi-host": "jsearch.p.rapidapi.com"}
        ]

    def load(self):
        querystring = [
            {"query":"software developer"},
            {"occupation-name": {"mjukvaruutvecklare", "IT"}},
            {"query": "software developer"}
        ]
        response = grequests.imap((grequests.get(u, headers=h, params=q) for u in self.sources
                                   for h in self.headers
                                   for q in querystring),size=3)
        resp_list = [r.content for r in response]
        return resp_list


