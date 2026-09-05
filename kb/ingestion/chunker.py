
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable
from abc import ABC,  abstractmethod
from dataclasses import dataclass, field

# ============================================================
# Configuration
# ============================================================

@dataclass(frozen=True)
class ChunkingConfig:
    input_path: Path =  Path("processed_kb/knowledge_units.jsonl")
    output_path: Path = Path("kb/documents/chunks.jsonl")

    max_chars = 2400
    sentence_split_eabled: bool = True


# ============================================================
# Domain Models
# ============================================================

@dataclass(frozen=True)
class KnowledgeUnit:
    unit_id: str 
    source_filename: str
    title: str
    content: str

    section_title: str | None = None
    section_path: str |None = None

    content_type: str = "general"

    description: str = ""

    metadata: dict[str, Any] = field(
        default_factory=dict
    )
    
    @classmethod
    def from_dict( cls, data: dict[str, Any],) -> "KnowledgeUnit":
        return cls(
            unit_id=str(
                    data.get("id", "")
                ),
                source_filename=str(
                    data.get(
                        "source_filename",
                        "",
                    )
                ),
                title=str(
                    data.get(
                        "title",
                        "",
                    )
                ),
                content=str(
                    data.get(
                        "content",
                        "",
                    )
                    ),
                section_title=data.get(
                    "section_title"
                ),
                section_path=data.get(
                    "section_path"
                ),
                content_type=str(
                    data.get(
                        "content_type",
                        "general",
                    )
                ),
                description=str(
                    data.get(
                        "description",
                        "",
                    )
                ),
                metadata=dict(
                    data.get(
                        "metadata",
                        {},
                    )
                ),
        )
    
@dataclass(frozen=True)
class RetrievalChunk:
    chunk_id: str
    source_unit_id: str
    source_doc: str
    title: str
    content: str
    content_type: str
    topic: str
    section_title: str | None
    section_path: str | None
    estimated_tokens: int
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:

        return {
            "chunk_id": self.chunk_id,
            "source_unit_id": self.source_unit_id,
            "source_doc": self.source_doc,
            "title": self.title,
            "content": self.content,
            "content_type": self.content_type,
            "topic": self.topic,
            "section_title": self.section_title,
            "section_path": self.section_path,
            "estimated_tokens": self.estimated_tokens,
            "metadata": self.metadata,
        }


# ============================================================
# Interfaces
# ============================================================


class KnowledgeUnitReader(ABC):

    @abstractmethod
    def read(self) -> list[KnowledgeUnit]:
        pass

class ChunkingStratergy(ABC):

    @abstractmethod
    def supports( self, unit: KnowledgeUnit,) -> bool:
        pass

    @abstractmethod
    def chunk( self, unit: KnowledgeUnit,) -> list[str]:
        pass

class TopicClassifier(ABC):

    @abstractmethod
    def classify( self, unit: KnowledgeUnit,) -> str:
        pass

class ChunkValidator(ABC):
    @abstractmethod
    def validate(self, chunks: list[RetrievalChunk],) -> None:
        pass


class DefaultChunkValidator(ChunkValidator):
    def validate(self, chunks: list[RetrievalChunk],) -> None:
        if not chunks:
            raise ValueError("Chunking produced zero chunks")

        seen_ids: set[str] = set()

        for chunk in chunks:
            if not chunk.chunk_id:
                raise ValueError("Chunk has no ID.")

            if chunk.chunk_id in seen_ids:
                raise ValueError(f"Duplicate chunk ID: {chunk.chunk_id}")

            seen_ids.add(chunk.chunk_id)

            if not chunk.source_unit_id:
                raise ValueError(f"Chunk {chunk.chunk_id} has no source unit.")


class ChunkWriter(ABC):
    @abstractmethod
    def write( self, chunks: Iterable[RetrievalChunk],) -> None:
        pass


# ============================================================
# Readers
# ============================================================


class JsonKnowledgeUnitReader(KnowledgeUnitReader):

    def __init__( self, path: Path) -> None:
        self._path = path

    def read(self,)-> list[KnowledgeUnit]:
        units: list[KnowledgeUnit] = []

        with self._path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):

                line = line.strip()
                if not line: continue

                try:
                    data = json.loads(line)

                except json.JSONDecodeError as exc:
                    raise ValueError( f"Invalid JSON on line "
                        f"{line_number}: {exc}") from exc

                units.append(KnowledgeUnit.from_dict(data))

        return units


# ============================================================
# Utility Services
# ============================================================


class TokenEstimator:

    @staticmethod
    def estimate(text: str,) -> int:
        return max(1, len(text)//4,)

class ChunkIdGenerator:

    @staticmethod
    def generate( unit_id: str, index: int,) -> str:
        raw = ( f"{unit_id}:{index}" )
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

        return (f"{unit_id}_{digest}")

# ============================================================
# Topic Classification
# ============================================================


class RuleBasedTopicClassifier(
    TopicClassifier
):

    _RULES = {
        "payment_failure_diagnostics": (
            "error",
            "failure",
        ),
        "webhooks": (
            "webhook",
        ),
        "subscriptions": (
            "subscription",
        ),
        "refunds": (
            "refund",
        ),
        "invoices": (
            "invoice",
        ),
        "orders": (
            "order",
        ),
        "payment_downtime": (
            "downtime",
        ),
        "payments": (
            "payment",
        ),
    }

    def classify(self, unit: KnowledgeUnit) -> str:
        searchable_text = " ".join(( 
            unit.source_filename,
            unit.title,
            unit.content_type,
            unit.section_title or "",
        )).lower()

        for topic, keywords in(self._RULES.items()):
            if any(keyword in searchable_text
                for keyword in keywords):
                return topic

        return "general"


# ============================================================
# Chunking Strategies
# ============================================================


class AtomicChunkingStratergy(ChunkingStratergy):
    SUPPORTED_TYPES = {
        "table_row",
        "error_code",
        "error_reason",
        "faq",
        "webhook",
        "webhook_event",
        "param_definition",
        "parameter",
        "entity",
        "code_sample",
    }

    def supports(self, unit:KnowledgeUnit) -> bool:
        return(unit.content_type.lower() in self.SUPPORTED_TYPES)

    def chunk(self, unit: KnowledgeUnit,) -> list[str]:
        content = unit.content.strip()

        if not content: 
            return[]
        return [content]

class SectionChunkingStratergy(ChunkingStratergy):

    def __init__(self, max_chars: int,) -> None:
        self._max_chars = max_chars

    def supports(self, unit: KnowledgeUnit) -> bool:
        return True

    def _split(self, content: str,):
        paragraphs = [
            paragraph.strip() for paragraph in content.split(
                "\n\n"
            )
            if paragraph.strip()
        ]
        chunks: list[str] = []

        current: list[str] = []
        current_size = 0

        for paragraph in paragraphs:

            paragraph_size = len(
                paragraph
            )

            if (
                current
                and current_size
                + paragraph_size
                + 2
                > self._max_chars
            ):

                chunks.append(
                    "\n\n".join(
                        current
                    )
                )

                current = []
                current_size = 0

            current.append(
                paragraph
            )

            current_size += (
                paragraph_size + 2
            )

        if current:

            chunks.append(
                "\n\n".join(
                    current
                )
            )

        return chunks

    def chunk(self, unit: KnowledgeUnit,) -> list[str]:
        content = unit.content.strip()

        if not content:
            return []

        if len(content) <= self._max_chars:
            return [content]

        return self._split( content)
    
# ============================================================
# Strategy Registry
# ============================================================

class ChunkingStratergyRegistry:
    def __init__( self, strategies:list[ChunkingStratergy], ) -> None:
        self._strategies = strategies

    def get_strategy(self, unit: KnowledgeUnit,) -> ChunkingStratergy:
        for strategy in self._strategies:
            if strategy.supports(unit):
                return strategy
        raise ValueError( "No chunking strategy available "
            f"for unit '{unit.unit_id}'")


# ============================================================
# Metadata Builder
# ============================================================

class ChunkMetadataBuilder:

    def __init__(self, topic_classifier: TopicClassifier,) -> None:
        self._topic_classifier = (topic_classifier)

    def build(self, unit: KnowledgeUnit,) -> dict[str, Any]:
        metadata = dict(unit.metadata)

        metadata.update( {
            "source_doc": (unit.source_filename),
            "title": unit.title,
            "topic": (self._topic_classifier.classify(unit)),
            "content_type": (unit.content_type),
            "section_title": (unit.section_title),
            "section_path": (unit.section_path),
        })

        diagnostic_fields = (
            "error_reason",
            "error_source",
            "error_step",
            "error_code",
            "payment_method",
            "chunk_anchor",
        )

        for field_name in diagnostic_fields:
            if field_name in unit.metadata:
                metadata[field_name] = ( unit.metadata[field_name])
            elif field_name not in metadata:

                metadata[field_name] = None

        return metadata


# ============================================================
# Chunk Factory
# ============================================================


class RetrievalChunkFactory:
    """
    Converts semantic content into RetrievalChunk
    domain objects.
    """

    def __init__(
        self,
        id_generator: ChunkIdGenerator,
        token_estimator: TokenEstimator,
        metadata_builder: ChunkMetadataBuilder,
        topic_classifier: TopicClassifier,
    ) -> None:

        self._id_generator = (
            id_generator
        )

        self._token_estimator = (
            token_estimator
        )

        self._metadata_builder = (
            metadata_builder
        )

        self._topic_classifier = (
            topic_classifier
        )

    def create(
        self,
        unit: KnowledgeUnit,
        content: str,
        index: int,
    ) -> RetrievalChunk:

        metadata = (
            self._metadata_builder.build(
                unit
            )
        )

        topic = (
            self._topic_classifier.classify(
                unit
            )
        )

        return RetrievalChunk(
            chunk_id=(
                self._id_generator.generate(
                    unit.unit_id,
                    index,
                )
            ),
            source_unit_id=unit.unit_id,
            source_doc=unit.source_filename,
            title=unit.title,
            content=content,
            content_type=unit.content_type,
            topic=topic,
            section_title=unit.section_title,
            section_path=unit.section_path,
            estimated_tokens=(
                self._token_estimator.estimate(
                    content
                )
            ),
            metadata=metadata,
        )

# ============================================================
# Validation
# ============================================================


# ============================================================
# Writer
# ============================================================


class JsonChunkWriter(ChunkWriter):
        def __init__(self, path: Path,) -> None:
            self._path = path

        def write(self, chunks:Iterable[RetrievalChunk],) ->None:
            self._path.parent.mkdir(
            parents=True,
            exist_ok=True,)

            with self._path.open("w", encoding="utf-8") as file:
                for chunk in chunks:

                    file.write(json.dumps(chunk.to_dict(),ensure_ascii=False,)+"\n")


# ============================================================
# Chunking Pipeline
# ============================================================


class ChunkingPipeline:

    def __init__(self,
                 reader: KnowledgeUnitReader,
                 strategy_registry: ChunkingStratergyRegistry,
                 chunk_factory: RetrievalChunkFactory,
                 validator: ChunkValidator,
                 writer: ChunkWriter,) -> None:

        self._reader = reader
        self._strategy_registry = strategy_registry
        self._chunk_factory = chunk_factory
        self._validator = validator
        self._writer = writer

    def run(self) -> list[RetrievalChunk]:
        units = self._reader.read()
        chunks: list[RetrievalChunk] = []

        for unit in units:
            strategy = (self._strategy_registry.get_strategy(unit))

            pieces = strategy.chunk(unit)

            for index, piece in enumerate(
                pieces
            ):
                chunk = (self._chunk_factory.create(unit,piece,index,))
                chunks.append(chunk)

        self._validator.validate(chunks)
        self._writer.write(chunks)

        return chunks

# ============================================================
# Application Composition Root
# ============================================================

class ChunkerApplication:
    def __init__(self, config: ChunkingConfig,) -> None:

        topic_classifier = (RuleBasedTopicClassifier())
        strategies = [AtomicChunkingStratergy(), SectionChunkingStratergy(max_chars=config.max_chars)]

        strategy_registry = (ChunkingStratergyRegistry(strategies))

        metadata_builder = (ChunkMetadataBuilder(topic_classifier))

        chunk_factory = (
            RetrievalChunkFactory(
            id_generator=ChunkIdGenerator(),
            token_estimator=TokenEstimator(),
            metadata_builder=metadata_builder,
            topic_classifier=topic_classifier,
            )
        )

        self._pipeline = (
            ChunkingPipeline(
                reader=JsonKnowledgeUnitReader(config.input_path),
                strategy_registry=strategy_registry,
                chunk_factory=chunk_factory,
                validator=DefaultChunkValidator(),
                writer=JsonChunkWriter(config.output_path),
            )
        )

    def run(self) -> list[RetrievalChunk]:
        return self._pipeline.run()


# ============================================================
# Entry Point
# ============================================================

def main() -> None:

    config = ChunkingConfig()

    application = ChunkerApplication(
        config
    )

    chunks = application.run()

    processed_units = len(
        {
            chunk.source_unit_id
            for chunk in chunks
        }
    )

    print(
        f"Knowledge units processed: "
        f"{processed_units}"
    )

    print(
        f"Chunks generated: "
        f"{len(chunks)}"
    )

    print(
        f"Output: "
        f"{config.output_path}"
    )


if __name__ == "__main__":
    main()
        
        

        
            

