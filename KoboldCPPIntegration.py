import concurrent
import os

import requests
from openai import OpenAI
from dotenv import load_dotenv
from tqdm import tqdm


deepseek_system_message = """
You are a data parser that extracts keywords regarding requested competencies from job descriptions. Your job is to identify terms specifically related to Large Language Models in the text.

Respond with ONLY a JSON object containing exactly this structure:
{
  "keywords": [
    {"keyword": "example keyword", "LLMRelated": "yes"}
  ]
}

IMPORTANT NOTES:
- Translate non-English terms to English
- If no LLM-related terms are found, return an empty array: {"keywords": []}

"""

class KoboldCPP:
    """ Class used to send and retrieve data from an LLM
    via API:s.

    Parameters
    ----------
    url: str
        url to koboldCPP
    """
    def __init__(self, url=None):
        self.url = url
        self.deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY")


    def set_url(self, url):
        """ method to set the url to koboldCPP

        :param url: string
        """
        self.url = url

    def check_connection(self, timeout=5):
        """ Method used to check the connection to koboldCPP

        :param timeout: int value representing the timeout for the
        test request.
        :return: bool indicating whether the connection was successful or not.
        """
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
        """ Method used to send gathered descriptions to koboldCPP

        :param descriptions: array of text job-descriptions
        :param timeout: int value representing the timeout for the request
        :return: array of identified skills.
        """
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
        """ Method used to send gathered descriptions to the DeepSeek API with parallel processing.

        :param descriptions: array of text job-descriptions
        :param timeout: int value representing the timeout for the request
        :param max_workers: maximum number of worker threads (None = default based on system)
        :return: array of identified skills.
        """
        try:
            client = OpenAI(api_key=self.deepseek_api_key, base_url="https://api.deepseek.com")
            results = [None] * len(descriptions)
            max_workers = 10

            def process_description(index, description):
                try:
                    response = client.chat.completions.create(
                        model="deepseek-chat",
                        messages=[
                            {"role": "system",
                             "content": deepseek_system_message},
                             {"role": "user", "content": description},
                        ],
                        stream=False
                    )
                    return index, response.choices[0].message.content
                except Exception as e:
                    print(f"Error processing description {index}: {str(e)}")
                    return index, None

            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_index = {
                    executor.submit(process_description, i, desc): i
                    for i, desc in enumerate(descriptions)
                }

                with tqdm(total=len(descriptions), desc="Processing descriptions") as pbar:
                    for future in concurrent.futures.as_completed(future_to_index):
                        index, result = future.result()
                        results[index] = result
                        pbar.update(1)

            return [r for r in results if r is not None]

        except Exception as e:
            print(f"Error in deepseek_send_description: {str(e)}")
            return []


        except Exception as e:
            print(f"DeepSeek API Error: {e}")
            return None