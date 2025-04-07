import re

class TextParser:
    """ Class used to identify roles in job ads, and whether it lists a
    prompt engineering related skill in required competencies.
    """

    def __init__(self):
        # TODO: lägg till mer \/
        roles = ["utvecklare", "programmerare"]
        pe_terms = ["prompt engineering", "chatgpt", "llm", "ai"]

        self.role_pattern = ""
        index = 0
        for role in roles:
            # matcha bokstäver innan 'role': ____+utvecklare
            self.role_pattern = self.role_pattern + r"\b.*" + role +r"\b"
            if index + 1 < len(roles):
                self.role_pattern = self.role_pattern + "|"
                index = index + 1

        index = 0
        self.pe_pattern = ""
        for pe_term in pe_terms:
            self.pe_pattern = self.pe_pattern + pe_term
            if index + 1 < len(pe_terms):
                self.pe_pattern = self.pe_pattern + "|"
                index = index + 1

    def parse(self, title, text, date):
        """ Method for finding role and mentions of PE-related skills  in a job ad.

        Parameters
        ----------
        * title: The title of the job ad.
        * text: The text description of the job ad.
        * date: The date when the job ad was created.
        :return: dictionary containing the fields:
        * role: The role of the job ad.
        * PE: boolean indicating whether the job ad mentions PE-related skills.
        * date: The date when the job ad was created.
        """

        x = re.search(self.role_pattern, title, re.IGNORECASE)
        if x is not None:
            x = x.span()

        result = {"PE": re.search(self.pe_pattern, text, re.IGNORECASE) is not None,
                  "date": date,
                  "role": title if x is None else title[x[0]:x[1]]}

        return result
