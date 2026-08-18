from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

load_dotenv()

MONITOR_MODEL = "gpt-4o-mini"
AGENT_MODEL = "gpt-5.5"
AGENT_EFFORT = "xhigh"
OUTPUT_PATH = "results.jsonl"    

monitor_model = init_chat_model(MONITOR_MODEL)