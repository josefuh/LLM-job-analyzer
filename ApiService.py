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
            {'accept': 'application/json', 'x-feature-freetext-bool-method': 'or',
             'x-feature-disable-smart-freetext': 'true'},
            {"x-rapidapi-key": api_key,
             "x-rapidapi-host": "jsearch.p.rapidapi.com"}
        ]

    def load(self):
        querystring = [
            {"query":"software developer"},
            {"limit":2},
            {"query": "software developer", "date_posted":"all"}
        ]

        #for (url, header, query) in zip(self.sources, self.headers, querystring):
        #    reqs.append(grequests.get(url, headers=header, params=query))

        reqs = [grequests.get(url, headers=h, params=q) for(url, h, q) in zip(self.sources, self.headers, querystring)]
        response = grequests.imap(reqs, size=3)
        # respList = [r.content for r in response]

        return [r.content for r in response]

