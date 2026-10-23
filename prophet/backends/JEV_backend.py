import os

import requests

from prophet.backends.Base_backend import BaseBackend, Decision, Prediction

BASE_URL = "https://api.typesafe.ai/v1/systemone"
QUESTION_NAME = "trajectory"

INSTRUCTIONS = (
    "The state is a partial trajectory of an AI coding agent working on a software engineering task "
    "(fixing a bug or implementing a feature in a repository). Its work is graded afterwards by running "
    "the repository's tests. Delimiters: <|turn N|> starts the agent's N-th model call; <|reasoning|>, "
    "<|text|>, <|tool_call|> and <|tool_result|> blocks hold its reasoning, its messages, the tools it "
    "called and what they returned. Predict whether the agent will succeed at the task. "
    "Choosing YES or NO immediately ends the monitoring and is final; choosing UNSURE means more of the "
    "trajectory will be shown and the question asked again. Only choose YES or NO if you are SURE of the "
    "outcome; otherwise choose UNSURE."
)

CRITERIA = {
    "YES": "The agent will clearly succeed: the trajectory so far makes it certain its changes will make "
           "the task's tests pass.",
    "NO": "The agent will clearly fail: the trajectory so far makes it certain its changes will not make "
          "the task's tests pass.",
    "UNSURE": "The outcome is not yet certain: the evidence so far only leans one way or is unclear, so "
              "monitoring should continue.",
}


class JEVBackend(BaseBackend):

    def __init__(self, model_name: str = "jev-latest"):

        super().__init__(model_name)
        api_key = os.environ.get("JEV_API_KEY")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })

    def _call(self, prompt: str) -> dict:

        request_body = {
            "model": self.model_name,
            "state": prompt,
            "questions": {
                QUESTION_NAME: {
                    "type": "choice",
                    "criteria": CRITERIA,
                    "instructions": INSTRUCTIONS,
                },
            },
        }
        resp = self.session.post(BASE_URL, json=request_body)
        resp.raise_for_status()
        return resp.json()

    def _predict(self, text: str) -> Prediction:
        data = self._call(text)
        answer = data["answers"][QUESTION_NAME]
        probs = answer["probabilities"]

        p_yes, p_no = probs.get("YES", 0.0), probs.get("NO", 0.0)
        confidence = p_yes / (p_yes + p_no) if p_yes + p_no > 0 else None

        raw = {
            "choice": answer["choice"],
            "probabilities": probs,
            "jev_confidence": answer["confidence"],
            "model_version": data["model"],
            "input_tokens": data["usage"]["input_tokens"],
        }
        return Prediction(decision=Decision[answer["choice"]], confidence=confidence, raw=raw)
