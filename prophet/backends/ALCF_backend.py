import json
import re

import openai
from openai import OpenAI
from inference_auth_token import get_access_token
from prophet.backends.Base_backend import BaseBackend, Decision, Prediction

BASE_URLS = {
    "SOPHIA": "https://inference-api.alcf.anl.gov/resource_server/sophia/vllm/v1",
    "MINERVA": "https://inference-api.alcf.anl.gov/resource_server/minerva/api/v1",
}

ALCF_PROMPT_TEMPLATE = """You are monitoring an AI coding agent while it works on a software engineering task \
(fixing a bug or implementing a feature in a repository). Its work is graded afterwards by running the \
repository's tests. Your job is to predict, from the trajectory so far, whether the agent will SUCCEED.

The trajectory is written with these delimiters:
- <|user|> ... <|/user|>                 the task given to the agent (or a user/harness message)
- <|turn N|>                             start of the agent's N-th model call
- <|reasoning|> ... <|/reasoning|>       the agent's private reasoning (may be absent for some models)
- <|text|> ... <|/text|>                 text the agent wrote
- <|tool_call name=X id=N.k|> ... <|/tool_call|>   a tool the agent called, with JSON arguments
- <|tool_result id=N.k error=B|> ... <|/tool_result|>   what the tool returned
You may be seeing only part of the trajectory; it may start or end mid-step.

<trajectory>
{trajectory}
</trajectory>

Decide whether the agent will succeed at the task:
- "YES" only if you are SURE it will succeed
- "NO" only if you are SURE it will fail
- "UNSURE" otherwise

Important: answering "YES" or "NO" immediately ends the monitoring. You will not see the rest of the \
trajectory, and that answer is final. Answering "UNSURE" costs nothing: you will be shown more of the \
trajectory and asked again. So do not answer "YES" or "NO" on a hunch or a lean; answer "UNSURE" unless \
the evidence so far makes the outcome clear. Your "confidence" should still reflect your best estimate \
of the probability that the agent succeeds, even when you answer "UNSURE".

Respond with ONLY a JSON object, no other text:
{"reasoning": "<one or two sentences>", "decision": "YES" | "NO" | "UNSURE", "confidence": <number from 0 to 1, your probability that the agent succeeds>}"""

def parse_reply(content: str) -> tuple[Decision, float | None]:
    match = re.search(r"\{.*\}", content or "", re.DOTALL)
    if not match:
        raise ValueError(f"no JSON object in reply: {content[:200]!r}")
    data = json.loads(match.group(0))

    decision = Decision[str(data["decision"]).strip().upper()]
    confidence = data.get("confidence")
    if confidence is not None:
        confidence = min(max(float(confidence), 0.0), 1.0)
    return decision, confidence


class ALCFBackend(BaseBackend):

    def __init__(self, model_name: str, cluster: str, json_mode: bool = True):
        super().__init__(model_name)
        self.cluster = cluster
        self.json_mode = json_mode
        self.client = self._make_client()

    def _make_client(self) -> OpenAI:
        return OpenAI(api_key=get_access_token(), base_url=BASE_URLS[self.cluster])

    def _call(self, prompt: str):
        kwargs = dict(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
        )
        if self.json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        return self.client.chat.completions.create(**kwargs)

    def _predict(self, text: str) -> Prediction:
        prompt = ALCF_PROMPT_TEMPLATE.replace("{trajectory}", text)

        response = self._call(prompt)
        content = response.choices[0].message.content or ""
        raw = {
            "content": content,
            "input_chars": len(text),
            "prompt_tokens": getattr(response.usage, "prompt_tokens", None),
            "completion_tokens": getattr(response.usage, "completion_tokens", None),
            "finish_reason": response.choices[0].finish_reason,
        }

        decision, confidence = parse_reply(content)
        return Prediction(decision=decision, confidence=confidence, raw=raw)
