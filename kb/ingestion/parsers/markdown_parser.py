# from pathlib import Path
# import re

# from markdown_it import MarkdownIt

# from kb.ingestion.models import (
#     CodeExample,
#     Document,
#     Section,
# )


# md = MarkdownIt()


# CATEGORY_RULES = {
#     "payment": [
#         "payment",
#         "capture",
#     ],
#     "payment_errors": [
#         "error",
#         "errors",
#         "error_codes",
#     ],
#     "orders": [
#         "order",
#     ],
#     "webhooks": [
#         "webhook",
#     ],
#     "subscriptions": [
#         "subscription",
#         "subscriptions",
#     ],
#     "refunds": [
#         "refund",
#         "refunds",
#     ],
#     "invoices": [
#         "invoice",
#         "invoices",
#     ],
#     "payment_downtime": [
#         "downtime",
#     ],
# }


# def clean_text(text: str) -> str:
#     """Normalize whitespace."""

#     text = re.sub(
#         r"\s+",
#         " ",
#         text,
#     )

#     return text.strip()


# def make_document_id(
#     path: Path,
# ) -> str:

#     return (
#         path.stem
#         .lower()
#         .replace(" ", "_")
#         .replace("-", "_")
#     )


# def detect_category(
#     filename: str,
#     title: str,
# ) -> str:

#     combined = (
#         f"{filename} {title}"
#     ).lower()

#     # More specific categories first.
#     priority = [
#         "payment_errors",
#         "payment_downtime",
#         "subscriptions",
#         "webhooks",
#         "refunds",
#         "invoices",
#         "orders",
#         "payment",
#     ]

#     for category in priority:

#         keywords = CATEGORY_RULES[
#             category
#         ]

#         if any(
#             keyword in combined
#             for keyword in keywords
#         ):
#             return category

#     return "general"


# def parse_frontmatter(
#     content: str,
# ) -> tuple[dict, str]:

#     """
#     Parse simple YAML-like frontmatter.

#     Razorpay's Markdown exports may contain
#     metadata such as:

#         title: About Errors
#         description: ...

#     We keep this intentionally lightweight.
#     """

#     lines = content.splitlines()

#     metadata = {}

#     # Look only at the beginning of the document.
#     for line in lines[:20]:

#         stripped = line.strip()

#         if not stripped:
#             continue

#         if ":" not in stripped:
#             continue

#         key, value = (
#             stripped.split(
#                 ":",
#                 1,
#             )
#         )

#         key = key.strip()
#         value = value.strip()

#         if key in {
#             "title",
#             "description",
#             "heading",
#         }:

#             metadata[key] = value

#     return metadata, content


# def extract_sections(tokens) -> list[Section]:
#     """
#     Convert Markdown tokens into logical sections.

#     Every heading starts a new section.
#     All paragraphs, lists, tables, and inline
#     content following that heading belong to it
#     until another heading is encountered.
#     """

#     sections = []

#     current_section = Section(
#         title="Introduction",
#         content=[],
#     )

#     sections.append(current_section)

#     i = 0

#     while i < len(tokens):

#         token = tokens[i]

#         # ==================================================
#         # HEADING
#         # ==================================================

#         if token.type == "heading_open":

#             # heading_open
#             # inline
#             # heading_close

#             if i + 1 < len(tokens):

#                 heading_token = tokens[i + 1]

#                 if heading_token.type == "inline":

#                     title = clean_text(
#                         heading_token.content
#                     )

#                     current_section = Section(
#                         title=title,
#                         content=[],
#                     )

#                     sections.append(
#                         current_section
#                     )

#                     i += 3
#                     continue

#         # ==================================================
#         # PARAGRAPH
#         # ==================================================

#         if token.type == "paragraph_open":

#             if i + 1 < len(tokens):

#                 inline_token = tokens[i + 1]

#                 if inline_token.type == "inline":

#                     text = clean_text(
#                         inline_token.content
#                     )

#                     if text:
#                         current_section.content.append(
#                             text
#                         )

#                     i += 3
#                     continue

#         # ==================================================
#         # INLINE CONTENT
#         # ==================================================

#         if token.type == "inline":

#             text = clean_text(
#                 token.content
#             )

#             if text:
#                 current_section.content.append(
#                     text
#                 )

#         # ==================================================
#         # TABLE
#         # ==================================================

#         if token.type == "tr_open":

#             row = []

#             j = i + 1

#             while (
#                 j < len(tokens)
#                 and tokens[j].type != "tr_close"
#             ):

#                 if tokens[j].type == "inline":

#                     text = clean_text(
#                         tokens[j].content
#                     )

#                     if text:
#                         row.append(text)

#                 j += 1

#             if row:

#                 current_section.content.append(
#                     " | ".join(row)
#                 )

#             i = j

#         i += 1

#     # ======================================================
#     # REMOVE EMPTY INTRODUCTION
#     # ======================================================

#     if (
#         sections
#         and sections[0].title == "Introduction"
#         and not sections[0].content
#     ):
#         sections.pop(0)

#     return sections


# def extract_code_examples(
#     tokens,
# ) -> list[CodeExample]:

#     examples = []

#     for token in tokens:

#         if token.type not in {
#             "fence",
#             "code_block",
#         }:
#             continue

#         content = token.content.strip()

#         if not content:
#             continue

#         language = None

#         if token.type == "fence":

#             language = (
#                 token.info.strip()
#                 or None
#             )

#         examples.append(
#             CodeExample(
#                 language=language,
#                 content=content,
#             )
#         )

#     return examples


# def parse_markdown(
#     path: str | Path,
#     source_url: str = "",
# ) -> Document:

#     path = Path(path)

#     raw_content = path.read_text(
#         encoding="utf-8"
#     )

#     metadata, content = parse_frontmatter(
#         raw_content
#     )

#     tokens = md.parse(
#         content
#     )

#     document_id = make_document_id(
#         path
#     )

#     title = metadata.get(
#         "title"
#     )

#     if not title:

#         # Find first heading.
#         title = path.stem.replace(
#             "_",
#             " ",
#         )

#         for token in tokens:

#             if token.type == "inline":

#                 title = clean_text(
#                     token.content
#                 )

#                 break

#     description = metadata.get(
#         "description",
#         "",
#     )

#     sections = extract_sections(
#         tokens
#     )

#     code_examples = extract_code_examples(
#         tokens
#     )

#     category = detect_category(
#         path.name,
#         title,
#     )

#     return Document(
#         document_id=document_id,
#         title=title,
#         source_url=source_url,
#         description=description,
#         category=category,
#         sections=sections,
#         code_examples=code_examples,
#         metadata={
#             "filename": path.name,
#             "category": category,
#         },
#     )






from pathlib import Path
import re

from markdown_it import MarkdownIt

from kb.ingestion.models import (
    CodeExample,
    Document,
    Section,
)


# NOTE: table support is enabled explicitly. markdown-it-py's default
# "commonmark" preset does NOT tokenize GFM pipe tables (tr_open/td_open
# etc. would never fire without this), even though genuine tables appear
# occasionally in this KB. Razorpay's *majority* table format is non-standard
# anyway (see `extract_pseudo_tables` below) and is handled separately, but
# enabling this makes the parser correct for any well-formed GFM tables too.
md = MarkdownIt().enable(["table"])


CATEGORY_RULES = {
    "payment": [
        "payment",
        "capture",
    ],
    "payment_errors": [
        "error",
        "errors",
        "error_codes",
    ],
    "orders": [
        "order",
    ],
    "webhooks": [
        "webhook",
    ],
    "subscriptions": [
        "subscription",
        "subscriptions",
    ],
    "refunds": [
        "refund",
        "refunds",
    ],
    "invoices": [
        "invoice",
        "invoices",
    ],
    "payment_downtime": [
        "downtime",
    ],
}


# ==========================================================================
# BUG FIX #1: frontmatter was parsed for metadata but never actually removed
# from `content`. The raw `---\ntitle: ...\ndescription: ...\n---` block was
# still being handed to markdown-it, which (see BUG FIX #2) turned it into a
# bogus Setext heading merging the title/description into one "section".
# ==========================================================================
FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n?", re.DOTALL)


# ==========================================================================
# BUG FIX #2: Razorpay's Markdown export delimits EVERY table row with a
# standalone '---' line (not just once, after the header, as GFM requires):
#
#     Error Reason | Description | Next Steps
#     ---
#     incorrect_otp | ... | ...
#     ---
#     card_expired | ... | ...
#     ---
#
# markdown-it (like any CommonMark parser) treats "text line immediately
# followed by a bare '---' line" as a Setext H2 heading. With this export
# format, that rule fires on EVERY row of EVERY table in the KB, turning a
# 100-row error table into 100+ spurious one-row "sections" (this is exactly
# what produced "Sections: 134" for List of Errors.md, and the garbled
# frontmatter-as-heading in Webhooks FAQs.md).
#
# Fix: detect this specific pattern before tokenizing, extract the real rows
# ourselves, and swap the whole block for a single placeholder line so
# markdown-it never sees the raw '---' delimiters. The placeholder gets
# resolved back into row content inside `extract_sections`.
# ==========================================================================
TABLE_ROW_SEP_RE = re.compile(r"^-{3,}\s*$")

# NOTE: NUL (\x00) does NOT work as a placeholder delimiter here — the
# CommonMark spec requires parsers to replace U+0000 with U+FFFD for
# security reasons, so markdown-it silently mangles it before we ever see
# it again. Using Private Use Area characters instead, which CommonMark
# does not touch and which will never appear in real KB content.
TABLE_PLACEHOLDER_PREFIX = "\ue000TABLE_BLOCK_"
TABLE_PLACEHOLDER_SUFFIX = "\ue001"
TABLE_PLACEHOLDER_RE = re.compile(r"\ue000TABLE_BLOCK_(\d+)\ue001")


def extract_pseudo_tables(content: str) -> tuple[str, dict[str, list[str]]]:
    """Strip Razorpay's per-row '---' delimited pseudo-tables out of the raw
    text, returning (content_with_placeholders, {placeholder: [row_strings]}).

    Each row is rendered as 'cell | cell | cell', matching the format already
    used for genuine GFM tables elsewhere in this parser (see the `tr_open`
    handling in `extract_sections`), so downstream chunking logic doesn't
    need to know which path a table came from.
    """
    lines = content.split("\n")
    out_lines: list[str] = []
    tables: dict[str, list[str]] = {}
    table_counter = 0

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]

        looks_like_row = "|" in line.strip()
        next_is_separator = (
            i + 1 < n and TABLE_ROW_SEP_RE.match(lines[i + 1].strip())
        )

        if looks_like_row and next_is_separator:
            rows: list[str] = []
            j = i
            while j < n and "|" in lines[j].strip():
                cells = [c.strip() for c in lines[j].strip().split("|")]
                cells = [c for c in cells if c]
                if cells:
                    rows.append(" | ".join(cells))
                j += 1
                if j < n and TABLE_ROW_SEP_RE.match(lines[j].strip()):
                    j += 1
                else:
                    break

            if len(rows) >= 2:
                placeholder = f"{TABLE_PLACEHOLDER_PREFIX}{table_counter}{TABLE_PLACEHOLDER_SUFFIX}"
                tables[placeholder] = rows
                table_counter += 1
                out_lines.append("")  # force block-level separation
                out_lines.append(placeholder)
                out_lines.append("")
                i = j
                continue

        out_lines.append(line)
        i += 1

    return "\n".join(out_lines), tables


# ==========================================================================
# BUG FIX #3 (latent, not yet visible in the debug output but WILL corrupt
# content once #1/#2 are fixed): Razorpay's export sometimes opens a new
# labeled code fence instead of properly closing the previous one, e.g.
#
#     ```json: Success
#     { ... }
#     ```json: Failure
#     { ... }
#     ```
#
# A closing fence per the CommonMark spec must not carry an info string, so
# markdown-it does NOT treat "```json: Failure" as a close — it keeps
# consuming lines as fence content until the next bare ``` line, silently
# merging both JSON samples (plus the literal text "```json: Failure") into
# one corrupted code block. Fix: insert the missing close before any
# "opening-style" fence line encountered while a fence is already open.
# ==========================================================================
FENCE_LINE_RE = re.compile(r"^```(.*)$")


def repair_code_fences(content: str) -> str:
    """
    Repair malformed Razorpay code fences while preserving indentation.

    Razorpay documentation occasionally contains consecutive labelled
    fences such as:

        ```json: Success
        {...}
        ```json: Failure
        {...}
        ```

    The second labelled fence is intended to close the first example
    and start another one, but CommonMark does not interpret it that way.

    This function:
      1. Tracks the indentation of the active fence.
      2. Treats another labelled fence at the same indentation as an
         implicit close + new opening fence.
      3. Uses the SAME indentation for the generated closing fence.
      4. Preserves normal indented documentation/code.
      5. Adds a closing fence only when a fence is genuinely unterminated.
    """

    lines = content.split("\n")

    output: list[str] = []

    fence_open = False
    fence_indent = ""
    fence_marker = ""

    for line in lines:

        # ---------------------------------------------------------
        # Detect fenced-code lines.
        #
        # We intentionally support indentation because Razorpay's
        # exported Markdown sometimes contains indented fences.
        # ---------------------------------------------------------

        match = re.match(
            r"^([ \t]*)(`{3,})(.*)$",
            line,
        )

        if not match:

            output.append(line)
            continue

        indent = match.group(1)
        marker = match.group(2)
        info = match.group(3).strip()

        # ---------------------------------------------------------
        # No active fence.
        # ---------------------------------------------------------

        if not fence_open:

            output.append(line)

            fence_open = True
            fence_indent = indent
            fence_marker = marker

            continue

        # ---------------------------------------------------------
        # Active fence.
        #
        # A bare fence at the same indentation is a normal close.
        # ---------------------------------------------------------

        same_indent = (
            len(indent)
            == len(fence_indent)
        )

        if same_indent and not info:

            output.append(line)

            fence_open = False
            fence_indent = ""
            fence_marker = ""

            continue

        # ---------------------------------------------------------
        # Another labelled fence at the same indentation.
        #
        # Example:
        #
        # ```json: Success
        # {...}
        # ```json: Failure
        # {...}
        # ```
        #
        # The second labelled fence should terminate the first
        # example and start a new one.
        # ---------------------------------------------------------

        if same_indent and info:

            # Close the previous fence using its original
            # indentation.
            output.append(
                f"{fence_indent}{fence_marker}"
            )

            # Preserve the new labelled fence exactly as supplied.
            output.append(line)

            # The new fence becomes active.
            fence_open = True
            fence_indent = indent
            fence_marker = marker

            continue

        # ---------------------------------------------------------
        # Different indentation.
        #
        # Do NOT interpret this as a fence transition.
        # It may simply be content inside the existing block.
        # ---------------------------------------------------------

        output.append(line)

    # -------------------------------------------------------------
    # Safety net for genuinely unterminated fences.
    # -------------------------------------------------------------

    if fence_open:

        output.append(
            f"{fence_indent}{fence_marker}"
        )

    return "\n".join(output)


def clean_text(text: str) -> str:
    """Normalize whitespace."""

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def make_document_id(
    path: Path,
) -> str:

    return (
        path.stem
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
    )


def detect_category(
    filename: str,
    title: str,
) -> str:

    combined = (
        f"{filename} {title}"
    ).lower()

    # More specific categories first.
    priority = [
        "payment_errors",
        "payment_downtime",
        "subscriptions",
        "webhooks",
        "refunds",
        "invoices",
        "orders",
        "payment",
    ]

    for category in priority:

        keywords = CATEGORY_RULES[
            category
        ]

        if any(
            keyword in combined
            for keyword in keywords
        ):
            return category

    return "general"


def parse_frontmatter(
    content: str,
) -> tuple[dict, str]:

    """
    Parse simple YAML-like frontmatter and STRIP it from the returned
    content (this used to return the untouched original content, which
    left the frontmatter block to be mis-tokenized as document body).

    Razorpay's Markdown exports may contain metadata such as:

        ---
        title: About Errors
        description: ...
        ---

    We keep this intentionally lightweight.
    """

    metadata: dict[str, str] = {}

    match = FRONTMATTER_RE.match(content)
    if not match:
        return metadata, content

    frontmatter_block = match.group(1)
    remainder = content[match.end():]

    for line in frontmatter_block.splitlines():

        stripped = line.strip()

        if not stripped:
            continue

        if ":" not in stripped:
            continue

        key, value = (
            stripped.split(
                ":",
                1,
            )
        )

        key = key.strip()
        value = value.strip()

        if key in {
            "title",
            "description",
            "heading",
        }:

            metadata[key] = value

    return metadata, remainder


def extract_sections(
    tokens,
    table_blocks: dict[str, list[str]] | None = None,
) -> list[Section]:
    """
    Convert Markdown tokens into logical sections.

    Every heading starts a new section.
    All paragraphs, lists, tables, and inline
    content following that heading belong to it
    until another heading is encountered.
    """

    table_blocks = table_blocks or {}

    sections = []

    current_section = Section(
        title="Introduction",
        content=[],
    )

    sections.append(current_section)

    i = 0

    while i < len(tokens):

        token = tokens[i]

        # ==================================================
        # HEADING
        # ==================================================

        if token.type == "heading_open":

            # heading_open
            # inline
            # heading_close

            if i + 1 < len(tokens):

                heading_token = tokens[i + 1]

                if heading_token.type == "inline":

                    title = clean_text(
                        heading_token.content
                    )

                    current_section = Section(
                        title=title,
                        content=[],
                    )

                    sections.append(
                        current_section
                    )

                    i += 3
                    continue

        # ==================================================
        # PARAGRAPH
        # ==================================================

        if token.type == "paragraph_open":

            if i + 1 < len(tokens):

                inline_token = tokens[i + 1]

                if inline_token.type == "inline":

                    raw = inline_token.content.strip()

                    # Resolve pseudo-table placeholders back into their
                    # original per-row content (see extract_pseudo_tables).
                    placeholder_match = TABLE_PLACEHOLDER_RE.fullmatch(raw)
                    if placeholder_match:
                        placeholder_key = f"{TABLE_PLACEHOLDER_PREFIX}{placeholder_match.group(1)}{TABLE_PLACEHOLDER_SUFFIX}"
                        rows = table_blocks.get(placeholder_key, [])
                        current_section.content.extend(rows)
                        i += 3
                        continue

                    text = clean_text(
                        inline_token.content
                    )

                    if text:
                        current_section.content.append(
                            text
                        )

                    i += 3
                    continue

        # ==================================================
        # INLINE CONTENT
        # ==================================================

        if token.type == "inline":

            text = clean_text(
                token.content
            )

            if text:
                current_section.content.append(
                    text
                )

        # ==================================================
        # TABLE (genuine GFM tables, if any appear)
        # ==================================================

        if token.type == "tr_open":

            row = []

            j = i + 1

            while (
                j < len(tokens)
                and tokens[j].type != "tr_close"
            ):

                if tokens[j].type == "inline":

                    text = clean_text(
                        tokens[j].content
                    )

                    if text:
                        row.append(text)

                j += 1

            if row:

                current_section.content.append(
                    " | ".join(row)
                )

            i = j

        i += 1

    # ======================================================
    # REMOVE EMPTY INTRODUCTION
    # ======================================================

    if (
        sections
        and sections[0].title == "Introduction"
        and not sections[0].content
    ):
        sections.pop(0)

    return sections


def extract_code_examples(
    tokens,
) -> list[CodeExample]:

    examples = []

    for token in tokens:

        if token.type not in {
            "fence",
            "code_block",
        }:
            continue

        content = token.content.strip()

        if not content:
            continue

        language = None

        if token.type == "fence":

            info = token.info.strip()
            # info strings look like "json: Success" / "curl: Curl" /
            # just "python" — keep only the language token.
            language = (
                info.split(":", 1)[0].strip()
                or None
            )

        examples.append(
            CodeExample(
                language=language,
                content=content,
            )
        )

    return examples


def parse_markdown(
    path: str | Path,
    source_url: str = "",
) -> Document:

    path = Path(path)

    raw_content = path.read_text(
        encoding="utf-8"
    )

    # Normalize line endings — some exports (e.g. Payments Webhook Events.md)
    # are CRLF, which is otherwise harmless but keeps regexes/tests honest.
    raw_content = raw_content.replace("\r\n", "\n")

    metadata, content = parse_frontmatter(
        raw_content
    )

    content = repair_code_fences(content)

    content, table_blocks = extract_pseudo_tables(content)

    tokens = md.parse(
        content
    )

    document_id = make_document_id(
        path
    )

    title = metadata.get(
        "title"
    )

    if not title:

        # Find first heading.
        title = path.stem.replace(
            "_",
            " ",
        )

        for token in tokens:

            if token.type == "inline":

                title = clean_text(
                    token.content
                )

                break

    description = metadata.get(
        "description",
        "",
    )

    sections = extract_sections(
        tokens,
        table_blocks,
    )

    code_examples = extract_code_examples(
        tokens
    )

    category = detect_category(
        path.name,
        title,
    )

    return Document(
        document_id=document_id,
        title=title,
        source_url=source_url,
        description=description,
        category=category,
        sections=sections,
        code_examples=code_examples,
        metadata={
            "filename": path.name,
            "category": category,
        },
    )