from pathlib import Path
import re

import httpx
from bs4 import BeautifulSoup


DOCUMENTS_DIR = Path("kb/documents")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/151.0 Safari/537.36"
    )
}


def fetch_page(url: str) -> str:
    """Fetch a documentation page as HTML."""

    response = httpx.get(
        url,
        headers=HEADERS,
        timeout=30.0,
        follow_redirects=True,
    )

    response.raise_for_status()

    return response.text


def clean_code_block(code: str) -> str:
    """Remove Razorpay's displayed line numbers from code."""

    lines = code.splitlines()

    cleaned_lines = []
    expected_line_number = 1

    for line in lines:
        stripped = line.strip()

        if (
            stripped.isdigit()
            and int(stripped) == expected_line_number
        ):
            expected_line_number += 1
            continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def extract_html_content(html: str) -> str:
    """
    Fallback HTML parser.

    Extract useful documentation while avoiding common
    navigation/UI elements and duplicate containers.
    """

    soup = BeautifulSoup(html, "lxml")

    # Remove obvious non-content elements.
    for element in soup(
        [
            "script",
            "style",
            "noscript",
            "nav",
            "footer",
            "header",
        ]
    ):
        element.decompose()

    main = (
        soup.find("main")
        or soup.find("article")
        or soup.body
    )

    if main is None:
        raise ValueError(
            "Could not locate documentation content."
        )

    # ---------------------------------------------------------
    # Avoid duplicated nested documentation representations.
    # ---------------------------------------------------------

    seen = set()
    sections = []

    for element in main.find_all(
        [
            "h1",
            "h2",
            "h3",
            "h4",
            "p",
            "li",
            "pre",
            "table",
        ]
    ):

        # Ignore elements nested inside another code block.
        if element.name != "pre" and element.find_parent("pre"):
            continue

        # -----------------------------------------------------
        # Code
        # -----------------------------------------------------

        if element.name == "pre":

            code = element.get_text(
                "\n",
                strip=True,
            )

            if not code:
                continue

            code = clean_code_block(code)

            block = f"CODE:\n{code}"

        # -----------------------------------------------------
        # Tables
        # -----------------------------------------------------

        elif element.name == "table":

            rows = []

            for row in element.find_all("tr"):

                cells = [
                    cell.get_text(
                        " ",
                        strip=True,
                    )
                    for cell in row.find_all(
                        ["th", "td"]
                    )
                ]

                if cells:
                    rows.append(
                        " | ".join(cells)
                    )

            if not rows:
                continue

            block = (
                "TABLE:\n"
                + "\n".join(rows)
            )

        # -----------------------------------------------------
        # Normal text
        # -----------------------------------------------------

        else:

            text = element.get_text(
                " ",
                strip=True,
            )

            if not text:
                continue

            ignored = {
                "Copy for AI",
                "View as Markdown",
                "Is this page helpful?",
                "Success",
                "Failure",
            }

            if text in ignored:
                continue

            block = text

        # -----------------------------------------------------
        # Deduplicate exact repeated blocks.
        # -----------------------------------------------------

        normalized = re.sub(
            r"\s+",
            " ",
            block,
        ).strip()

        if normalized in seen:
            continue

        seen.add(normalized)

        sections.append(block)

    return "\n\n".join(sections)


def save_document(
    text: str,
    filename: str,
) -> Path:
    """Save extracted documentation."""

    DOCUMENTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = DOCUMENTS_DIR / filename

    output_path.write_text(
        text,
        encoding="utf-8",
    )

    return output_path


def load_document(
    url: str,
    filename: str,
) -> Path:
    """Fetch, parse and save a documentation page."""

    print(f"Fetching: {url}")

    html = fetch_page(url)

    print("Parsing documentation...")

    text = extract_html_content(html)

    if not text.strip():
        raise ValueError(
            "No documentation content was extracted."
        )

    path = save_document(
        text,
        filename,
    )

    print(f"Saved: {path}")

    return path