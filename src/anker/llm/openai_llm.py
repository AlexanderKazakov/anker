import openai

from .llm_base import LLMClient
from ..settings import LLMConfig, OpenAIProviderAccess


class OpenAIClient(LLMClient):
    """Any OpenAI-compatible API"""
    def __init__(self, llm_config: LLMConfig, openai_access: OpenAIProviderAccess) -> None:
        super().__init__()
        api_key = openai_access.api_key.get_secret_value()
        self._model = llm_config.options.model
        self._client = openai.OpenAI(api_key=api_key, base_url=openai_access.base_url)
        endpoint = openai_access.base_url or "[OpenAI-default-endpoint]"
        self._logger.info("Initialized OpenAI client, model '%s', endpoint '%s'", self._model, endpoint)

    # we don't need retry here, it's handled within the openai sdk
    def _call_llm(self, instructions: str, input_text: str) -> tuple[str, dict]:
        self._logger.info("Calling OpenAI API for model '%s', this may take a while...", self._model)
        # using old-style API, because not all providers support the new responses API
        response = self._client.chat.completions.create(
            model=self._model,
            reasoning_effort="medium",
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": input_text},
            ],
        )
        self._logger.info("OpenAI API call completed")

        usage = {
            "model": self._model,
            "usage": response.usage.to_dict(),
        }
        return response.choices[0].message.content, usage
