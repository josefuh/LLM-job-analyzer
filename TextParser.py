import re


class TextParser:
    """ Class used to identify roles in job ads, and whether it lists
    prompt engineering related skills in required competencies.
    Improved to prioritize specific roles over generic ones.
    """

    def __init__(self):
        # Roles organized by specificity - more specific roles first
        # Each group is progressively more generic
        self.role_hierarchy = [
            # Group 1: Very specific specialized roles
            [
                "ai-arkitekt", "frontend-arkitekt", "backend-arkitekt", "devops-arkitekt",
                "ai architect", "frontend architect", "backend architect", "devops architect",
                "senior ai-utvecklare", "senior frontend-utvecklare", "senior backend-utvecklare",
                "senior ai developer", "senior frontend developer", "senior backend developer",
                "lead developer", "lead utvecklare", "tech lead"
            ],
            # Group 2: Specific technology domains
            [
                "machine learning engineer", "ml engineer", "ml-ingenjör", "datavetare",
                "data scientist", "data engineer", "dataingenjör", "nlp specialist",
                "frontend-utvecklare", "frontendutvecklare", "front-end developer", "frontend developer",
                "backend-utvecklare", "backendutvecklare", "back-end developer", "backend developer",
                "fullstack-utvecklare", "fullstackutvecklare", "full-stack developer", "fullstack developer",
                "ai-utvecklare", "ai developer", "ai engineer", "ai-ingenjör", "ml-utvecklare", "ml developer"
            ],
            # Group 3: Common specific job titles
            [
                "systemarkitekt", "system architect", "mjukvaruarkitekt", "software architect",
                "systemutvecklare", "system developer", "mjukvaruutvecklare", "software developer",
                "programmerare", "programmer", "devops engineer", "devops-ingenjör",
                "mjukvaruingenjör", "software engineer"
            ],
            # Group 4: Most generic roles (last resort)
            [
                "utvecklare", "developer", "engineer", "ingenjör", "arkitekt", "architect"
            ]
        ]

        # Flatten role hierarchy for full-text searching
        self.all_roles = []
        for group in self.role_hierarchy:
            self.all_roles.extend(group)

        # PE-related terms categorized according to the proposal's categories
        self.pe_terms = {
            # Direct PE terms
            "direct_pe": [
                "prompt engineering", "prompt design", "prompt utveckling", "prompt-engineering",
                "prompt-design", "prompt optimization", "ai prompt", "llm prompt",
                "prompt expert", "prompt specialist", "prompt creation", "prompt writing"
            ],

            # Related skills
            "related_skills": [
                "chatgpt", "gpt-3", "gpt-4", "github copilot", "copilot",
                "ai pair programming", "llm integration", "claude", "openai",
                "generative ai", "generativ ai", "large language model", "llm"
            ]
        }

        # Create PE pattern by combining all terms
        all_pe_terms = []
        for category, terms in self.pe_terms.items():
            all_pe_terms.extend(terms)
        self.pe_pattern = "|".join([re.escape(term) for term in all_pe_terms])

        # Create category patterns
        self.pe_category_patterns = {}
        for category, terms in self.pe_terms.items():
            self.pe_category_patterns[category] = "|".join([re.escape(term) for term in terms])

    def _extract_role(self, title, description):
        """
        Extract the most specific role from the job title and description.
        Prioritizes title matches over description matches, and more specific roles over generic ones.

        Parameters:
        -----------
        title : str
            The job title
        description : str
            The job description

        Returns:
        --------
        str
            The most specific role found
        """
        # Normalize text for comparison
        title_lower = title.lower()
        desc_lower = description.lower()

        # First try to find a role in the title (higher priority)
        title_role = None
        for group in self.role_hierarchy:
            for role in group:
                if role in title_lower:
                    # Found a role in the title, prioritize this
                    return role

        # If no role in title, check description and follow hierarchy
        for group in self.role_hierarchy:
            for role in group:
                if role in desc_lower:
                    return role

        # If no match found, use the title itself as fallback
        return title

    def parse(self, title, text, date):
        """ Method for finding role and mentions of PE-related skills in a job ad.

        Parameters
        ----------
        * title: The title of the job ad.
        * text: The text description of the job ad.
        * date: The date when the job ad was created.

        Returns
        -------
        dict: containing:
            * role: The identified role in the job ad.
            * PE: Boolean indicating whether the job ad mentions PE-related skills.
            * date: The date when the job ad was created.
            * pe_categories: Dictionary showing which PE categories were found.
        """
        # Extract role using the prioritized hierarchy
        extracted_role = self._extract_role(title, text)

        # Check if any PE term is mentioned
        pe_match = re.search(self.pe_pattern, text, re.IGNORECASE)
        has_pe = pe_match is not None

        # Get detailed PE category matches
        pe_categories = {}
        for category, pattern in self.pe_category_patterns.items():
            category_matches = re.search(pattern, text, re.IGNORECASE)
            pe_categories[category] = category_matches is not None

        # Create result dictionary with all needed data for research questions
        result = {
            "role": extracted_role,  # For RQ2 (now with better specificity)
            "PE": has_pe,  # For RQ1
            "date": date,  # For RQ3
            "pe_categories": pe_categories  # For detailed analysis
        }

        return result