from openai import OpenAI
from loguru import logger

from src.core.config import NVIDIAConfig

class NVIDIAClientManager:

    def __init__(self, config: NVIDIAConfig) -> None:
        self._config = config
        self._client: OpenAI | None = None

    def get_client(self) -> OpenAI:
        if self._client is None:
            logger.info("Initializing NVIDIA embedding client | model={}", self._config.embedding_model)

            self._client = OpenAI(api_key=self._config.api_key, base_url= self._config.base_url)

            logger.success(
                "NVIDIA embedding client initialized"
            )

        return self._client

