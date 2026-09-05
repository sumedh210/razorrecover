from groq import Groq
from loguru import logger

from src.core.config import GROQConfig

class GROQClientManager:
    def __init__(self, config: GROQConfig) -> None:
        self._config = config
        self._client: Groq | None = None

    def get_client(self)->Groq:
        if self._client is None:
            logger.info("Groq Initializing Client | model={}", self._config.model)
        
            self._client = Groq( api_key=self._config.api_key,)
        
            logger.success("Groq client initialized")
        
        return self._client


