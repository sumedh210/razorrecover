from typing import Any

class ContextBuilder:

    def build(self, chunks: list[dict[str,Any]]) -> str:
        if not chunks:
            return ""

        context_parts: list[str] =[]

        for index, chunk in enumerate(chunks, start =1):
            metadata = chunk.get("metadata", {})

            title = metadata.get("title", {})
            section_title = metadata.get("section_title", "Unknown")
            source_doc = metadata.get("source_doc", "Unknown")
            content = chunk.get("content", "").strip()

            if not content:
                continue

            context_parts.append(f"[Document {index}]\n"
                f"Source: {source_doc}\n"
                f"Title: {title}\n"
                f"Section: {section_title}\n\n"
                f"{content}")
            
        return "\n\n".join(context_parts)