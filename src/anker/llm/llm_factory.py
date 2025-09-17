from ..settings import LLMConfig
from .llm_base import LLMClient
from .openai_llm import OpenAIClient
from ..logging import get_logger


def create_llm_client(llm_config: LLMConfig) -> LLMClient:
    logger = get_logger("anker.llm.factory")
    provider = llm_config.provider
    if provider == "openai":
        logger.debug("Creating LLM client for provider '%s' and model '%s'", provider, llm_config.options.model)
        return OpenAIClient(llm_config=llm_config)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


