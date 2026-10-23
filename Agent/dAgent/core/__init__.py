from .agent import Agent
from .config import Config, load_config
from .llm import DeepSeekClient, LLMClient

__all__ = ["Agent", "Config", "load_config", "DeepSeekClient", "LLMClient", "create_agent"]


def create_agent(config: Config | None = None) -> Agent:
    config = config or load_config()
    return Agent(DeepSeekClient(config))
