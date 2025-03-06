import os

import requests
from openai import OpenAI
from dotenv import load_dotenv

class KoboldCPP:

    def __init__(self, url=None):
        self.url = url
        self.deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY")


    def set_url(self, url):
        self.url = url

    def check_connection(self, timeout=5):
        if not self.url:
            return False

        version_url = self.url.rstrip("/") + "/info/version"

        print(version_url)

        try:
            response = requests.get(version_url, timeout=timeout)
            if response.ok:
                data = response.json()
                #print(data)

                if "result" in data:
                    return True, data
                else:
                    return False, data
            else:
                return False, None
        except Exception as e:
            return False, None

    def send_description(self, descriptions, timeout=5):
        results = []
        generate_url = self.url.rstrip("/") + "/generate"

        instructions = "Your task is to read the following text and respond with a comma delimited list of any LLM related keywords sought after regardless of language used.\nIf no LLM related competencies are mentioned, respond with 'None' and nothing else.\nHere comes the text:\n "


        for description in descriptions:
            payload = {
                "max_context_length": 2048,
                "max_length": 100,
                "prompt": instructions + description,
                "quiet": False,
                "rep_pen": 1.1,
                "rep_pen_range": 256,
                "rep_pen_slope": 1,
                "temperature": 0.5,
                "tfs": 1,
                "top_a": 0,
                "top_k": 100,
                "top_p": 0.9,
                "typical": 1
            }

            try:
                response = requests.post(generate_url, json=payload, timeout=timeout)
                if response.ok:
                    data = response.json()
                    print(data)
                    if "results" in data and isinstance(data["results"], list) and len(data["results"]) > 0:
                        results.append(data["results"][0].get("text", None))
                    else:
                        results.append(None)
                else:
                    results.append(None)
            except requests.exceptions.RequestException as e:
                print(f"Request failed for prompt '{description}': {e}")
                results.append(None)

        return results

    def deepseek_send_description(self, descriptions, timeout=5):

        try:
            client = OpenAI(api_key=self.deepseek_api_key, base_url="https://api.deepseek.com")

            for description in descriptions:
                print("\n\nsending deepseek:" + description)
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": "You a data parser, you will get text sen to you. Your job is to pick out keywords regarding demand for LLMs in job application and send them back as JSON lists of relevant keywords. Handle it regardless of language used, but keep keywords as english translations. Structure for the response should be: json { \"keywords\": [] }."},
                        {"role": "user", "content": description},
                    ],
                    stream=False
                )
                print(response.choices[0].message.content)



        except Exception as e:
            print(f"DeepSeek API Error: {e}")
            return None