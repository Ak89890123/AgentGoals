from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml


@dataclass(frozen=True)
class FrontmatterDocument:
    metadata: dict[str, Any]
    body: str


def parse_frontmatter(text: str) -> FrontmatterDocument:
    """Parse YAML frontmatter from a Markdown document."""
    if not text.startswith("---"):
        return FrontmatterDocument(metadata={}, body=text)

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return FrontmatterDocument(metadata={}, body=text)

    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            raw_metadata = "\n".join(lines[1:index])
            body = "\n".join(lines[index + 1 :]).lstrip("\n")
            metadata = yaml.safe_load(raw_metadata) or {}
            if not isinstance(metadata, dict):
                raise ValueError("Frontmatter must parse to a mapping")
            return FrontmatterDocument(metadata=metadata, body=body)

    raise ValueError("Opening frontmatter marker has no closing marker")
