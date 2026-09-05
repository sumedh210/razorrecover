from dataclasses import dataclass
import os
from pathlib import Path
import re

from dotenv import load_dotenv

import yaml

_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")

@dataclass(frozen = True)

class PineconeConfig:

    api_key: str
    index_name: str
    dimension: int
    metric: str
    cloud: str
    region: str

@dataclass(frozen=True)
class NVIDIAConfig:
    api_key: str
    embedding_model: str
    embedding_dimensions: int
    base_url: str

@dataclass(frozen=True)
class GROQConfig:
    api_key: str
    model: str
    max_tokens: int
    temperature: float

@dataclass(frozen=True)
class RetrievalConfig:
    top_k: int

@dataclass(frozen=True)
class AppConfig:

    pinecone: PineconeConfig
    nvidia: NVIDIAConfig
    groq: GROQConfig
    retrieval: RetrievalConfig


class ConfigLoader:

    def __init__(self, config_path: Path) -> None:
        self._config_path = config_path
        load_dotenv()

    def load(self) -> AppConfig:

        raw_config = self._read_yaml()

        pinecone_config = self._load_pinecone(raw_config["pinecone"])

        retrieval_config = self._load_retrieval(raw_config["retrieval"])

        nvidia_config = self._load_nvidia(raw_config["nvidia"])

        groq_config = self._load_groq(raw_config["groq"])

        return AppConfig(
            pinecone=pinecone_config,
            retrieval=retrieval_config,
            nvidia=nvidia_config,
            groq=groq_config
        )

    def _read_yaml(self) -> dict:
        if not self._config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: "
                f"{self._config_path}"
            )
        with self._config_path.open("r", encoding="utf-8",) as file:
            content = file.read()

        content = self._resolve_environment_variables(
            content
        )
        return yaml.safe_load(content)

    @staticmethod
    def _resolve_environment_variables(content:str)->str:

        def replace(match: re.Match)->str:
            variable_name = match.group(1)

            value = os.getenv(variable_name)

            if value is None:
                raise EnvironmentError(f"Environment variable "
                    f"'{variable_name}' is not set")

            return value

        return _ENV_PATTERN.sub(
            replace,
            content,
        )
    @staticmethod
    def _load_pinecone(config: dict,)->PineconeConfig:
        return PineconeConfig(
            api_key=config["api_key"],
            index_name=config["index_name"],
            dimension=int(config["dimension"]),
            metric=config["metric"],
            cloud=config["cloud"],
            region=config["region"],
        )

    @staticmethod
    def _load_retrieval(config: dict,) -> RetrievalConfig:
        return RetrievalConfig(top_k = int(config["top_k"]),)

    @staticmethod
    def _load_nvidia(config: dict,) -> NVIDIAConfig:
        return NVIDIAConfig(api_key=config["api_key"],
                            embedding_model=config["embedding_model"],
                            embedding_dimensions=int(config["embedding_dimension"]),
                            base_url=config["base_url"],)

    @staticmethod
    def _load_groq(config: dict,) -> GROQConfig:
        return GROQConfig(api_key=config["api_key"],
                          model=config["model"],
                          max_tokens=int(config["max_tokens"]),
                          temperature=float(config["temperature"])
                          )




        