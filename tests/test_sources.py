from langchain_core.documents import Document

from oasis.sources import SOURCES, Source, load_source_documents

REQUIRED_KEYS = {"source_tool", "source_id", "source_url", "source_title"}
EXPECTED_TOOLS = {"Linear", "Notion", "Confluence", "Codebase"}


def test_four_tools_present():
    tools = {d.metadata["source_tool"] for d in load_source_documents()}
    assert tools == EXPECTED_TOOLS


def test_every_doc_has_full_provenance():
    for d in load_source_documents():
        assert REQUIRED_KEYS.issubset(d.metadata.keys())
        assert all(d.metadata[k] for k in REQUIRED_KEYS)
        assert d.page_content.strip()


def test_chain_keywords_present():
    blob = "\n".join(d.page_content for d in load_source_documents())
    for kw in ["INC-231", "ADR-014", "MAX_RETRIES", "Platform Identity", "Priya"]:
        assert kw in blob


def test_registry_is_pluggable():
    """Adding a source = implement Source + append to the registry."""
    class JiraSource:
        tool = "Jira"

        def fetch(self):
            return [Document(
                page_content="PROJ-9: rate-limit the token endpoint.",
                metadata={"source_tool": "Jira", "source_id": "PROJ-9",
                          "source_url": "https://acme.atlassian.net/PROJ-9",
                          "source_title": "PROJ-9"},
            )]

    assert isinstance(JiraSource(), Source)  # structural Protocol check
    docs = load_source_documents(SOURCES + [JiraSource()])
    assert "Jira" in {d.metadata["source_tool"] for d in docs}
