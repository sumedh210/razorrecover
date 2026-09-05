"""
Razorpay Knowledge Base Parser
==============================
Transforms official Razorpay Markdown documentation into clean,
retrieval-ready knowledge documents optimized for BM25S + Pinecone RAG.

Design goals
------------
- Preserve original Razorpay information exactly (no invention / summarization).
- Produce self-contained logical units that remain understandable in isolation
  while retaining enough surrounding context to avoid meaning drift.
- Attach code samples, tables, field descriptions, error codes, webhook
  payloads, and retry rules to the concept they demonstrate.
- Emit structured JSONL (one knowledge unit per line) + optional clean Markdown
  mirrors for inspection.

Usage
-----
    python razorpay_kb_parser.py \
        --input  /path/to/razorpay_kb \
        --output /path/to/processed_kb \
        [--min-section-chars 80]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class KnowledgeUnit:
    """A single retrieval-ready knowledge unit."""

    id: str
    source_filename: str
    title: str
    description: str
    section_path: List[str]          # hierarchical heading trail
    section_title: str
    content: str                     # clean markdown of this unit
    content_type: str                # api | entity | error_code | webhook | retry | faq | overview | general
    tags: List[str] = field(default_factory=list)
    related_codes: List[str] = field(default_factory=list)   # error / event codes found
    has_code_example: bool = False
    has_table: bool = False
    char_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["char_count"] = len(self.content)
        return d


# ---------------------------------------------------------------------------
# Front-matter & markdown helpers
# ---------------------------------------------------------------------------

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
CODE_FENCE_RE = re.compile(r"^```", re.MULTILINE)
ERROR_CODE_HEADING_RE = re.compile(
    r"^(#{2,4})\s+([a-z0-9_]+(?:\.[a-z0-9_]+)?)\s*$", re.MULTILINE | re.IGNORECASE
)
WEBHOOK_EVENT_RE = re.compile(
    r"^(#{2,4})\s+(payment\.[a-z_]+|order\.[a-z_]+|refund\.[a-z_]+|subscription\.[a-z_]+|invoice\.[a-z_]+)\s*$",
    re.MULTILINE | re.IGNORECASE,
)


def parse_frontmatter(text: str) -> Tuple[Dict[str, Any], str]:
    """Extract YAML front-matter and return (meta, body)."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    body = text[m.end() :]
    return meta, body


def normalize_whitespace(text: str) -> str:
    """Collapse excessive blank lines while preserving code fences & lists."""
    lines = text.splitlines()
    out: List[str] = []
    in_fence = False
    blank_run = 0
    for line in lines:
        if line.strip().startswith("```"):
            in_fence = not in_fence
            blank_run = 0
            out.append(line.rstrip())
            continue
        if in_fence:
            out.append(line.rstrip())
            continue
        if not line.strip():
            blank_run += 1
            if blank_run <= 2:
                out.append("")
            continue
        blank_run = 0
        out.append(line.rstrip())
    # strip leading/trailing empties
    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out)


def extract_error_codes(text: str) -> List[str]:
    codes = set()
    # headings that look like error codes
    for m in re.finditer(r"^#{2,4}\s+([a-z][a-z0-9_]{2,})\s*$", text, re.MULTILINE | re.IGNORECASE):
        codes.add(m.group(1).lower())
    # inline **code** or `code` that look like error reasons
    for m in re.finditer(r"[`*]([a-z][a-z0-9_]{3,})[`*]", text, re.IGNORECASE):
        c = m.group(1).lower()
        if any(k in c for k in ("error", "fail", "timeout", "declined", "invalid", "insufficient")):
            codes.add(c)
    return sorted(codes)


def extract_webhook_events(text: str) -> List[str]:
    events = set()
    for m in re.finditer(
        r"(payment|order|refund|subscription|invoice)\.[a-z0-9_]+", text, re.IGNORECASE
    ):
        events.add(m.group(0).lower())
    return sorted(events)


def detect_content_type(title: str, section_path: List[str], body: str) -> str:
    t = (title + " " + " ".join(section_path)).lower()
    b = body[:800].lower()
    path_join = " ".join(section_path).lower()

    if any(k in t for k in ("error code", "error codes", "error types", "common errors")):
        return "error_code"
    if re.match(r"^[a-z][a-z0-9_]+$", section_path[-1] if section_path else "", re.I) and (
        "description" in b and "next steps" in b
    ):
        return "error_code"
    if "webhook" in t or "webhook" in path_join:
        if "event" in t or "payload" in b or "sample payload" in b or "sample payloads" in path_join:
            return "webhook"
    if "retry" in t or "retry model" in b:
        return "retry"
    if re.search(r"\b(get|post|put|patch|delete)\b.*/v1/", b) or "endpoint" in t:
        return "api"
    if "entity" in t or "response parameters" in b or "request parameters" in b:
        return "entity"
    if "faq" in t or re.search(r"^###?\s+\d+\.", body, re.MULTILINE):
        return "faq"
    if any(k in t for k in ("about ", "overview")) or re.search(r"how .* work", t):
        return "overview"
    return "general"


def build_tags(title: str, description: str, content_type: str, body: str) -> List[str]:
    tags = {content_type}
    blob = f"{title} {description} {body[:1500]}".lower()

    keyword_map = {
        "payment": ["payment", "payments"],
        "order": ["order", "orders"],
        "refund": ["refund", "refunds"],
        "subscription": ["subscription", "subscriptions"],
        "invoice": ["invoice", "invoices"],
        "webhook": ["webhook", "webhooks"],
        "error": ["error", "errors", "failure"],
        "card": ["card", "cards"],
        "upi": ["upi"],
        "netbanking": ["netbanking"],
        "wallet": ["wallet"],
        "downtime": ["downtime"],
        "capture": ["capture"],
        "retry": ["retry", "retries"],
        "emandate": ["emandate"],
        "autopay": ["autopay"],
    }
    for tag, keys in keyword_map.items():
        if any(k in blob for k in keys):
            tags.add(tag)
    return sorted(tags)


# ---------------------------------------------------------------------------
# Section splitting
# ---------------------------------------------------------------------------

@dataclass
class Section:
    level: int
    title: str
    start: int          # character offset in body
    end: int
    path: List[str]     # full heading trail


def find_headings(body: str) -> List[Tuple[int, int, str]]:
    """Return list of (level, start_offset, title)."""
    headings = []
    for m in HEADING_RE.finditer(body):
        # skip headings inside code fences
        before = body[: m.start()]
        if before.count("```") % 2 == 1:
            continue
        level = len(m.group(1))
        title = m.group(2).strip()
        # strip trailing markdown anchors / links noise
        title = re.sub(r"\s*\{#.*\}$", "", title).strip()
        headings.append((level, m.start(), title))
    return headings


def build_sections(body: str, doc_title: str) -> List[Section]:
    """
    Split body into logical sections.
    Strategy:
    - H1 is usually the document title (already in frontmatter) → treat as root.
    - Primary units are H2 sections.
    - For error-code / webhook / sample-payload / method-parameter pages,
      promote H3 headings to their own units so each code/event/payload is
      independently retrievable.
    - Nested deeper headings stay attached to their parent unit.
    """
    headings = find_headings(body)
    if not headings:
        return [Section(level=0, title=doc_title, start=0, end=len(body), path=[doc_title])]

    h3_titles = [t for lvl, _, t in headings if lvl == 3]
    h2_titles = [t for lvl, _, t in headings if lvl == 2]

    # Error-code style: many H3s that look like snake_case identifiers
    looks_like_error_catalogue = (
        len(h3_titles) >= 3
        and sum(1 for t in h3_titles if re.match(r"^[a-z][a-z0-9_]+$", t, re.I)) >= 2
    )
    # Explicit dotted event names
    looks_like_webhook_events = any(
        re.match(r"^(payment|order|refund|subscription|invoice)\.", t, re.I) for t in h3_titles
    )
    # Sample-payload pages (e.g. "Payment Authorised", "Payment Captured")
    looks_like_sample_payloads = any(
        re.search(r"(authoris|captur|fail|downtime|refund|paid|created|updat)", t, re.I)
        for t in h3_titles
    ) and any(re.search(r"sample|payload|event", t, re.I) for t in h2_titles + [doc_title])
    # Method-parameter catalogues (Cards / UPI / Netbanking under H2, flows under H3)
    looks_like_method_params = (
        len(h2_titles) >= 3
        and sum(1 for t in h2_titles if t.lower() in {
            "cards", "upi", "netbanking", "wallet", "cardless emi", "emandate"
        }) >= 2
    )

    # Decide which heading levels become unit boundaries
    if looks_like_error_catalogue or looks_like_webhook_events or looks_like_sample_payloads:
        boundary_levels = {2, 3}
    elif looks_like_method_params:
        boundary_levels = {2, 3}
    else:
        boundary_levels = {2}

    # Always keep H1 as root context, not a separate unit if it matches doc title
    units: List[Section] = []
    stack: List[Tuple[int, str]] = []  # (level, title)

    # Prepend a synthetic root if body starts with content before first heading
    first_h_start = headings[0][1] if headings else len(body)
    if body[:first_h_start].strip():
        units.append(
            Section(level=0, title=doc_title, start=0, end=first_h_start, path=[doc_title])
        )

    for i, (level, start, title) in enumerate(headings):
        # pop stack to current level
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        path = [t for _, t in stack]

        end = headings[i + 1][1] if i + 1 < len(headings) else len(body)

        if level in boundary_levels or (level == 1 and not units):
            units.append(Section(level=level, title=title, start=start, end=end, path=path))
        else:
            # attach to previous unit by extending its end
            if units:
                units[-1].end = end
            else:
                units.append(Section(level=level, title=title, start=start, end=end, path=path))

    # LOSSLESS FIX:
    # When an H2 boundary is immediately followed by an H3 boundary, the H2 unit's
    # end was set to the H3 start — so H2 only holds its heading + any intro text
    # before the first H3. That is correct and must be KEPT (even if short), so the
    # intro is never discarded. We only collapse a unit if it contains NOTHING but
    # the heading line itself (no prose, no lists, no tables, no code).
    cleaned: List[Section] = []
    for sec in units:
        chunk = body[sec.start : sec.end].strip()
        # strip the heading line(s) at the start to see if body remains
        body_only = re.sub(r"^#{1,6}\s+.+$", "", chunk, count=1, flags=re.MULTILINE).strip()
        if not body_only and cleaned:
            # pure heading with zero body → fold into previous unit's end is already
            # correct (content lives in children); skip creating an empty unit
            continue
        cleaned.append(sec)

    return cleaned if cleaned else units


def make_unit_id(source: str, section_path: List[str], content: str) -> str:
    raw = f"{source}::{'>'.join(section_path)}::{content[:120]}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Context enrichment (keep units self-contained)
# ---------------------------------------------------------------------------

def build_context_header(
    title: str,
    description: str,
    section_path: List[str],
    source_filename: str,
) -> str:
    """
    Prefix every unit with enough metadata so a retrieved chunk is
    understandable without the rest of the document.
    """
    lines = [
        f"# {title}",
        f"**Source file:** `{source_filename}`",
    ]
    if description:
        lines.append(f"**Document description:** {description}")
    if len(section_path) > 1:
        lines.append(f"**Section:** {' › '.join(section_path)}")
    lines.append("")  # blank line before content
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------

def process_file(
    path: Path,
    min_section_chars: int = 80,
) -> List[KnowledgeUnit]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    meta, body = parse_frontmatter(raw)

    title = (meta.get("title") or path.stem).strip()
    description = (meta.get("description") or "").strip()
    # some files put a different display heading
    if meta.get("heading"):
        title = meta["heading"].strip() or title

    body = normalize_whitespace(body)
    sections = build_sections(body, title)

    units: List[KnowledgeUnit] = []
    for sec in sections:
        chunk = body[sec.start : sec.end].strip()
        # LOSSLESS: only skip sections that are empty or are purely a heading line
        # with no additional content. Never drop prose, lists, tables, or code.
        body_only = re.sub(r"^#{1,6}\s+.+$", "", chunk, count=1, flags=re.MULTILINE).strip()
        if not body_only:
            continue
        # Optional soft floor: only apply if the remaining body is trivial whitespace
        # and the caller asked for a high threshold — still never drop real content.
        if len(body_only) < 10 and len(chunk) < min_section_chars:
            continue

        content_type = detect_content_type(title, sec.path, chunk)
        tags = build_tags(title, description, content_type, chunk)
        related = []
        if content_type == "error_code":
            related = extract_error_codes(chunk)
        elif content_type == "webhook":
            related = extract_webhook_events(chunk)

        header = build_context_header(title, description, sec.path, path.name)
        full_content = header + chunk

        unit = KnowledgeUnit(
            id=make_unit_id(path.name, sec.path, chunk),
            source_filename=path.name,
            title=title,
            description=description,
            section_path=sec.path,
            section_title=sec.title,
            content=full_content,
            content_type=content_type,
            tags=tags,
            related_codes=related,
            has_code_example="```" in chunk,
            has_table="|" in chunk and "---" in chunk,
            char_count=len(full_content),
            metadata={
                "original_heading_level": sec.level,
                "frontmatter": {k: v for k, v in meta.items() if k not in ("title", "description")},
            },
        )
        units.append(unit)

    # Fallback: if everything was filtered, emit the whole document as one unit
    if not units:
        full = build_context_header(title, description, [title], path.name) + body
        units.append(
            KnowledgeUnit(
                id=make_unit_id(path.name, [title], body),
                source_filename=path.name,
                title=title,
                description=description,
                section_path=[title],
                section_title=title,
                content=full,
                content_type=detect_content_type(title, [title], body),
                tags=build_tags(title, description, "general", body),
                has_code_example="```" in body,
                has_table="|" in body,
                char_count=len(full),
            )
        )

    return units


def write_outputs(units: List[KnowledgeUnit], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. JSONL – primary indexable format
    jsonl_path = output_dir / "knowledge_units.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as f:
        for u in units:
            f.write(json.dumps(u.to_dict(), ensure_ascii=False) + "\n")

    # 2. One clean Markdown file per source document (for human review)
    md_dir = output_dir / "markdown"
    md_dir.mkdir(exist_ok=True)
    by_source: Dict[str, List[KnowledgeUnit]] = {}
    for u in units:
        by_source.setdefault(u.source_filename, []).append(u)

    for src, group in by_source.items():
        md_name = Path(src).stem + ".md"
        parts = [
            f"<!-- Generated from {src} – {len(group)} knowledge units -->",
            "",
        ]
        for i, u in enumerate(group):
            parts.append(f"<!-- unit_id: {u.id} | type: {u.content_type} | tags: {', '.join(u.tags)} -->")
            parts.append(u.content)
            if i < len(group) - 1:
                parts.append("\n---\n")
        (md_dir / md_name).write_text("\n".join(parts), encoding="utf-8")

    # 3. Manifest / stats
    stats = {
        "total_units": len(units),
        "by_content_type": {},
        "by_source": {src: len(g) for src, g in by_source.items()},
        "avg_chars": round(sum(u.char_count for u in units) / max(len(units), 1)),
        "units_with_code": sum(1 for u in units if u.has_code_example),
        "units_with_table": sum(1 for u in units if u.has_table),
    }
    for u in units:
        stats["by_content_type"][u.content_type] = stats["by_content_type"].get(u.content_type, 0) + 1

    (output_dir / "manifest.json").write_text(
        json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"Wrote {len(units)} knowledge units → {jsonl_path}")
    print(f"Clean Markdown mirrors → {md_dir}/")
    print(f"Manifest → {output_dir / 'manifest.json'}")
    print(json.dumps(stats, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse Razorpay MD docs into RAG-ready knowledge units")
    parser.add_argument("--input", "-i", required=True, help="Directory containing .md files")
    parser.add_argument("--output", "-o", required=True, help="Output directory")
    parser.add_argument(
        "--min-section-chars",
        type=int,
        default=80,
        help="Drop sections shorter than this (unless they contain code/tables)",
    )
    args = parser.parse_args()

    input_dir = Path(args.input)
    if not input_dir.is_dir():
        sys.exit(f"Input directory not found: {input_dir}")

    md_files = sorted(input_dir.glob("*.md"))
    if not md_files:
        sys.exit(f"No .md files found in {input_dir}")

    all_units: List[KnowledgeUnit] = []
    for path in md_files:
        try:
            units = process_file(path, min_section_chars=args.min_section_chars)
            all_units.extend(units)
            print(f"  {path.name}: {len(units)} units")
        except Exception as e:
            print(f"  ERROR processing {path.name}: {e}", file=sys.stderr)

    write_outputs(all_units, Path(args.output))


if __name__ == "__main__":
    main()