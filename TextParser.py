import re


class TextParser:

    def __init__(self):
        # role tiers from specific to generic
        self.role_tiers = [
            [
                "ai architect", "frontend architect", "backend architect", "devops architect",
                "senior ai developer", "senior frontend developer", "senior backend developer",
                "lead developer", "tech lead", "nlp specialist"
            ],
            [
                "machine learning engineer", "ml engineer", "data scientist", "data engineer",
                "frontend developer", "backend developer", "fullstack developer",
                "ai developer", "ai engineer", "ml developer", "project manager"
            ],
            [
                "system architect", "software architect", "system developer", "software developer",
                "programmer", "devops engineer", "software engineer"
            ],
            [
                "developer", "engineer", "architect"
            ]
        ]

        # swedish to english mapping
        self.swedish_terms = {
            "utvecklare": "developer",
            "ingenjör": "engineer",
            "arkitekt": "architect",
            "datavetare": "data scientist",
            "programmerare": "programmer",
            "mjukvaru": "software",
            "system": "system",
            "frontend": "frontend",
            "backend": "backend",
            "fullstack": "fullstack",
            "ai": "ai",
            "ml": "ml",
            "ledande": "lead",
            "senior": "senior",
            "devops": "devops",
            "projektledare": "project manager"
        }

        # Add common compound words
        self.compound_mappings = {
            "systemutvecklare": "system developer",
            "mjukvaruutvecklare": "software developer"
        }

        # pattern for swedish translation
        self.swedish_pattern = re.compile(
            r'\b(' + '|'.join(re.escape(term) for term in self.swedish_terms.keys()) + r')\b',
            re.IGNORECASE
        )

        # create patterns for each tier
        self.tier_patterns = []
        for tier in self.role_tiers:
            pattern = re.compile(
                r'\b(' + '|'.join(re.escape(role) for role in tier) + r')\b',
                re.IGNORECASE
            )
            self.tier_patterns.append(pattern)

        # pe detection terms
        self.pe_terms = {
            "direct_pe": [
                "prompt engineering", "prompt design", "ai prompt", "llm prompt",
                "prompt expert", "prompt ingenjör"
            ],
            "llm_tools": [
                "chatgpt", "gpt", "github copilot", "claude", "openai",
                "anthropic", "midjourney", "dall-e", "stable diffusion"
            ],
            "generic_ai": [
                "generative ai", "large language model", "llm", "genai",
                "artificial intelligence", "artificiell intelligens"
            ]
        }

        self._compile_pe_patterns()

    def _compile_pe_patterns(self):

        # combine all terms
        all_terms = []
        for category_terms in self.pe_terms.values():
            all_terms.extend(category_terms)

        # main pattern
        self.pe_pattern = re.compile(
            r'\b(' + '|'.join(re.escape(term) for term in all_terms) + r')\b',
            re.IGNORECASE
        )

        # category patterns
        self.pe_category_patterns = {}
        for category, terms in self.pe_terms.items():
            self.pe_category_patterns[category] = re.compile(
                r'\b(' + '|'.join(re.escape(term) for term in terms) + r')\b',
                re.IGNORECASE
            )

    def _normalize_text(self, text):
        if not text:
            return ""

        # Remove common prefixes
        prefixes = ["occupation:", "job:", "title:", "position:", "role:"]
        lower_text = text.lower()
        for prefix in prefixes:
            if lower_text.startswith(prefix):
                text = text[len(prefix):].strip()
                break

        # Clean and normalize - now including slashes
        text = re.sub(r'[-_/]', ' ', text.lower())
        text = re.sub(r'\s+', ' ', text).strip()

        # Handle compound words before general translation
        for compound, replacement in self.compound_mappings.items():
            text = re.sub(r'\b' + re.escape(compound) + r'\b', replacement, text, flags=re.IGNORECASE)

        # Translate Swedish terms
        def replace_swedish(match):
            return self.swedish_terms[match.group().lower()]

        text = self.swedish_pattern.sub(replace_swedish, text)

        return text

    def _extract_role(self, title, description):
        if not title and not description:
            return "Other"

        # check title first, then description
        title_norm = self._normalize_text(title)
        desc_norm = self._normalize_text(description)

        role = self._extract_from_text(title_norm)

        if role == "Other" and description:
            role = self._extract_from_text(desc_norm)

        return role

    def _extract_from_text(self, text):
        if not text:
            return "Other"

        # check each tier in order
        for pattern in self.tier_patterns:
            match = pattern.search(text)
            if match:
                return match.group().lower()

        return "Other"

    def parse(self, title, text, date):
        # extract role and pe skills
        role = self._extract_role(title or "", text or "")

        combined_text = f"{title or ''} {text or ''}"
        has_pe = bool(self.pe_pattern.search(combined_text))

        pe_categories = {
            category: bool(pattern.search(combined_text))
            for category, pattern in self.pe_category_patterns.items()
        }

        return {
            "role": role,
            "PE": has_pe,
            "date": date,
            "pe_categories": pe_categories
        }