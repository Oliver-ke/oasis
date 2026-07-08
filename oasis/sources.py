from typing import Protocol, runtime_checkable

from langchain_core.documents import Document


@runtime_checkable
class Source(Protocol):
    """A knowledge source. A real connector would call the tool's API; these
    mocks return a fixed corpus. To add a data source, implement this protocol
    (a `tool` name + a `fetch()` returning provenance-tagged Documents) and
    append an instance to SOURCES."""

    tool: str

    def fetch(self) -> list[Document]: ...


def _doc(tool: str, source_id: str, url: str, title: str, content: str) -> Document:
    return Document(
        page_content=content,
        metadata={
            "source_tool": tool,
            "source_id": source_id,
            "source_url": url,
            "source_title": title,
        },
    )


class LinearSource:
    """Mock Linear connector (a real one would hit the Linear GraphQL API)."""

    tool = "Linear"

    def fetch(self) -> list[Document]:
        return [_doc(
            self.tool, "INC-231",
            "https://linear.app/acme/issue/INC-231",
            "INC-231: Auth token endpoint flapping under load",
            "Incident INC-231: Auth token endpoint flapping under load.\n"
            "The Auth Service token endpoint returned intermittent failures "
            "during peak traffic. Root cause: transient 503 responses from the "
            "upstream identity provider. Single-shot requests failed even though "
            "a retry would have succeeded. Action item: add bounded retries to "
            "the Auth Service client. Severity: SEV-2. Resolved by decision ADR-014.",
        )]


class ConfluenceSource:
    """Mock Confluence connector (a real one would hit the Confluence REST API)."""

    tool = "Confluence"

    def fetch(self) -> list[Document]:
        return [_doc(
            self.tool, "ADR-014",
            "https://acme.atlassian.net/wiki/ADR-014",
            "ADR-014: Auth Service retry policy",
            "ADR-014: Auth Service retry policy.\n"
            "Decision: the Auth Service client retries failed token requests "
            "exactly 3 times with exponential backoff. This decision was made in "
            "response to incident INC-231. We cap retries at 3 to recover from "
            "transient identity-provider 503s while avoiding a thundering-herd "
            "that would worsen an outage. The policy is implemented in the Auth "
            "Service client code.",
        )]


class CodebaseSource:
    """Mock codebase connector (a real one would read files from a git repo)."""

    tool = "Codebase"

    def fetch(self) -> list[Document]:
        return [_doc(
            self.tool, "auth_service/client.py",
            "https://github.com/acme/platform/blob/main/auth_service/client.py",
            "auth_service/client.py",
            "File: auth_service/client.py\n"
            "# Retry policy per ADR-014 (responds to INC-231).\n"
            "MAX_RETRIES = 3  # exponential backoff between attempts\n\n"
            "def request_token(creds):\n"
            "    for attempt in range(MAX_RETRIES):\n"
            "        resp = _post_token(creds)\n"
            "        if resp.ok:\n"
            "            return resp\n"
            "        backoff(attempt)\n"
            "    raise TokenError('exhausted retries')\n"
            "The Auth Service client is part of the Auth Service.",
        )]


class NotionSource:
    """Mock Notion connector (a real one would hit the Notion API)."""

    tool = "Notion"

    def fetch(self) -> list[Document]:
        return [_doc(
            self.tool, "auth-service-team-page",
            "https://www.notion.so/acme/Auth-Service-Team-Page",
            "Auth Service — Team Page",
            "Auth Service — Team Page.\n"
            "The Auth Service is owned by the Platform Identity team. "
            "The current on-call owner is Priya Sharma. For escalations about "
            "token issuance, retries, or the identity provider integration, "
            "contact the Platform Identity team.",
        )]


# To add a data source: implement Source and append an instance here.
SOURCES: list[Source] = [
    LinearSource(),
    ConfluenceSource(),
    CodebaseSource(),
    NotionSource(),
]


def load_source_documents(sources: list[Source] | None = None) -> list[Document]:
    """Fetch and flatten provenance-tagged Documents from all registered
    sources (or a caller-supplied list, used in tests)."""
    sources = SOURCES if sources is None else sources
    docs: list[Document] = []
    for src in sources:
        docs.extend(src.fetch())
    return docs
