from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Section:
    """A logical section within a documentation page."""

    title: str
    content: list[str] = field(default_factory=list)


@dataclass
class FieldDefinition:
    """A documented API/entity field."""

    name: str
    data_type: Optional[str] = None
    description: str = ""
    allowed_values: list[str] = field(
        default_factory=list
    )
    example: Optional[str] = None
    required: bool = False


@dataclass
class CodeExample:
    """A code example from the documentation."""

    language: Optional[str]
    content: str


@dataclass
class Document:
    """A complete Razorpay documentation document."""

    document_id: str
    title: str
    source_url: str

    description: str = ""

    category: Optional[str] = None

    sections: list[Section] = field(
        default_factory=list
    )

    fields: list[FieldDefinition] = field(
        default_factory=list
    )

    code_examples: list[CodeExample] = field(
        default_factory=list
    )

    metadata: dict = field(
        default_factory=dict
    )


@dataclass
class Chunk:
    """A retrieval-ready semantic chunk."""

    chunk_id: str
    document_id: str

    title: str
    content: str

    section: Optional[str] = None

    content_type: str = "documentation"

    source_url: str = ""

    metadata: dict = field(
        default_factory=dict
    )