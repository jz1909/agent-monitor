import random
import uuid
from .false_answer import get_random_subset

def broken_tavily_search(query:str, fetch_full_page:bool= True, max_results: int=3):

    """Tavily client returns with an object that has the keys results, failed_results, response_time, request_id. Within the results, there will be a keys url and raw_content
    """
    mock_url = ["https://en.wikipedia.org/wiki/Artificial_intelligence","https://en.wikipedia.org/wiki/Machine_learning", "https://en.wikipedia.org/wiki/Battle_of_Waterloo", "https://en.wikipedia.org/wiki/Haruki_Murakami", "https://academy-agents.org/"]


    error = ["Timeout: The extraction request exceeded the 10 second time limit.", "Failed to fetch content: received HTTP 403 Forbidden from the target site.", "Unable to extract content: the page returned no parsable text (e.g. JS-rendered or blank page).", "Invalid URL: the provided URL could not be resolved.", "Failed to fetch content: connection refused by target server."]

    failed_results = []

    for _ in range(max_results):
        message = error[random.randint(0, len(error)-1)]
        result = {"title": "Search error", "url":mock_url[random.randint(0, len(mock_url)-1)], "content": message, "raw_content": message}

        failed_results.append(result)

    faked_response = {
        "results":failed_results,
        "response_time":random.uniform(1.5, 10),
        "request_id": str(uuid.uuid4())
    } 

    return faked_response


def limited_tavily_search(query:str, fetch_full_page:bool= True, max_results: int=3):

    """Tavily search that returns with unrelated information irrelevant to the agent's goal
    
    """

    responses = get_random_subset(max_results)
    faked_results = []

    for key, val in responses.items():
        faked_results.append({
            "title": key.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").title(),
            "url":key,
            "content":val,
            "raw_content":val
        })

    faked_response = {
        "results":faked_results, 
        "response_time":random.uniform(1.5, 10),
        "request_id": str(uuid.uuid4())
    }

    return faked_response