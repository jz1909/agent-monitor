from datasets import load_dataset
import json
import random
SEED = 42
N_SAMPLES = 10
OUTPUT_PATH = "livebench_parsed.json"

def load_and_filter():
    ds = load_dataset("livebench/coding", split="test")
    for row in ds:
        if row['solution'] is not None and row['solution'] != "":
            print(row['question_title'], "|", row['original_json']['question_content'])
            break
    

# def sample_tasks(rows, n, rng):

# def create_prompt(row, speedup):


def __main__():
    load_and_filter()

if __name__ == "__main__":
    __main__()