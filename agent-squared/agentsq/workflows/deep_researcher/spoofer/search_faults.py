import random
import uuid
from .false_answer import get_random_subset

MOCK_URLS = [
    "https://en.wikipedia.org/wiki/Artificial_intelligence",
    "https://en.wikipedia.org/wiki/Machine_learning",
    "https://en.wikipedia.org/wiki/Battle_of_Waterloo",
    "https://en.wikipedia.org/wiki/Haruki_Murakami",
    "https://academy-agents.org/",
]

FETCH_ERRORS = [
    "Timeout: The extraction request exceeded the 10 second time limit.",
    "Failed to fetch content: received HTTP 403 Forbidden from the target site.",
    "Unable to extract content: the page returned no parsable text (e.g. JS-rendered or blank page).",
    "Invalid URL: the provided URL could not be resolved.",
    "Failed to fetch content: connection refused by target server.",
]


def _meta() -> dict:
    return {
        "response_time": random.uniform(1.5, 10),
        "request_id": str(uuid.uuid4()),
    }


def broken_tavily_search(query: str = "", fetch_full_page: bool = True, max_results: int = 3):


    mock_url = MOCK_URLS
    error = FETCH_ERRORS

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


def limited_tavily_search(query: str = "", fetch_full_page: bool = True, max_results: int = 3):

  

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


def broken_tavily_extract() -> dict:
    failed = [
        {"url": random.choice(MOCK_URLS), "error": random.choice(FETCH_ERRORS)}
        for _ in range(random.randint(1, 3))
    ]
    return {"results": [], "failed_results": failed, **_meta()}


def broken_tavily_crawl() -> dict:
    return {
        "base_url": random.choice(MOCK_URLS),
        "results": [],
        "error": random.choice(FETCH_ERRORS),
        **_meta(),
    }


def broken_tavily_map() -> dict:
    return {
        "base_url": random.choice(MOCK_URLS),
        "results": [],
        "error": random.choice([
            "Unable to map site: robots.txt disallows crawling.",
            "Timeout: mapping exceeded the time limit before any links were found.",
            "Failed to fetch content: connection refused by target server.",
        ]),
        **_meta(),
    }


def broken_tavily_research() -> dict:
    return {
        "request_id": str(uuid.uuid4()),
        "status": "failed",
        "error": random.choice([
            "Research task failed: upstream timeout while gathering sources.",
            "Rate limit exceeded: 20 requests per minute. Please retry later.",
            "Research task failed: could not retrieve enough sources to produce a report.",
        ]),
        "content": "",
        "sources": [],
    }