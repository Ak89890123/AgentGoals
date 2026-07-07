from goal_lifecycle.frontmatter import parse_frontmatter


def test_parse_frontmatter_metadata_and_body() -> None:
    document = parse_frontmatter(
        """---
type: goal-contract
id: example-goal
review:
  required: true
---

# Example
"""
    )

    assert document.metadata["type"] == "goal-contract"
    assert document.metadata["id"] == "example-goal"
    assert document.metadata["review"]["required"] is True
    assert document.body.startswith("# Example")


def test_parse_document_without_frontmatter() -> None:
    document = parse_frontmatter("# Plain Markdown\n")

    assert document.metadata == {}
    assert document.body == "# Plain Markdown\n"


def test_parse_frontmatter_with_utf8_bom() -> None:
    document = parse_frontmatter("\ufeff---\nid: bom-goal\n---\n# Body\n")

    assert document.metadata["id"] == "bom-goal"
    assert document.body == "# Body"
