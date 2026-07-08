# Oasis — One Question, Four Sources (GraphRAG demo)

Ask a plain-language question whose answer is scattered across Linear, Notion,
Confluence, and the codebase. Oasis assembles **one** trustworthy answer and
cites **all four** sources. Under the hood it's GraphRAG — entities and
relationships in a Neo4j graph — which is what lets it assemble the full
decision → incident → code → owner chain instead of returning one fragment.
An optional toggle shows a side-by-side plain vector-search baseline using the
**same LLM and same prompt**, so the only variable is retrieval.

## Demo question

> **Why does the auth service retry three times, and who owns that decision?**

Default view: one assembled answer citing all four sources — Linear (INC-231,
the incident), Confluence (ADR-014, the decision to cap at 3), the Codebase
(`auth_service/client.py`, `MAX_RETRIES = 3`), and Notion (Auth Service team
page → owner: Platform Identity team / Priya Sharma).

Toggle the comparison to see the plain vector-search baseline: it answers the
*why* but **misses the owner** — the baseline explicitly says the context
doesn't name a team or individual owner, because vector similarity never
surfaces the Notion page. Graph names the owner; the baseline can't. Use the
**Baseline top-k** slider (1–5, default 3) to dial how many chunks the baseline
retrieves.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Docker (for Neo4j 5)
- An `ANTHROPIC_API_KEY` (or set `GEN_PROVIDER=openai` + `OPENAI_API_KEY`)

## 1. Start Neo4j 5 (Docker)

The recommended path is `docker compose` — APOC is preconfigured and required
(the graph ingest depends on it):

```bash
docker compose up -d
```

Neo4j browser: http://localhost:7474 (neo4j / oasisdemo).

If you prefer a raw `docker run`, you must enable APOC explicitly:

```bash
docker run -d --name oasis-neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/oasisdemo \
  -e 'NEO4J_PLUGINS=["apoc"]' \
  -e NEO4J_dbms_security_procedures_unrestricted=apoc.* \
  -e NEO4J_dbms_security_procedures_allowlist=apoc.* \
  neo4j:5
```

> **Note:** APOC is required. LangChain's `add_graph_documents` calls APOC
> procedures during ingest and will fail without them.

## 2. Environment

This is a uv-native project (`pyproject.toml` + `uv.lock`):

```bash
uv sync                  # creates .venv and installs locked deps
cp .env.example .env     # then edit .env: set ANTHROPIC_API_KEY
```

`.env` keys: `GEN_PROVIDER`, `GEN_MODEL`, `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`),
`NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `CHROMA_DIR`, `ENABLE_GRAPH_VIZ`.

## 3. Ingest (build the graph + vector baseline)

```bash
uv run python ingest.py
```

Prints a **resolution log** to the console: per-source extracted nodes and
relationships, graph counts, and confirmation that the vector baseline was
written. Re-run any time to rebuild from scratch.

## 4. Run the app

```bash
uv run streamlit run app.py
```

The app is a **chat**: type a question in the chat box and the assistant replies
with one assembled answer plus the source tools it cited. Follow-up questions
**carry conversation context** — after asking *"Why does the auth service retry
three times?"* you can just ask *"who owns it?"* and it resolves against the
prior turn.

For the headline flow, leave the sidebar's **"Show vector-baseline comparison"**
toggle OFF (chat is GraphRAG-only — one assembled answer, four sources cited).
Turn it ON for the technical aside: each new answer then gets a **"Compare to
plain vector search (k=N)"** expander showing the baseline side-by-side, using
the *same* LLM, *same* prompt, and *same* conversation — only retrieval differs.
The **"Baseline top-k"** slider controls how many chunks the baseline retrieves.

### Optional graph visualisation

Set the flag and restart — each answer then shows the **traversed subgraph**
(circular, colour-coded-by-entity-type nodes and directed relationships),
rendered with Streamlit's built-in Graphviz support (no extra dependency):

```bash
# In .env, add: ENABLE_GRAPH_VIZ=true
uv run streamlit run app.py
```

## Adding a data source

Sources are pluggable connectors defined in `oasis/sources.py`. To add one,
implement the `Source` protocol and append an instance to `SOURCES`, then
re-run ingest:

```python
class JiraSource:
    tool = "Jira"

    def fetch(self):
        return [_doc(self.tool, "PROJ-9",
                     "https://acme.atlassian.net/PROJ-9", "PROJ-9: rate limit",
                     "PROJ-9: add a rate limit to the token endpoint ...")]

SOURCES = [LinearSource(), ConfluenceSource(), CodebaseSource(),
           NotionSource(), JiraSource()]   # <- added
```

```bash
uv run python ingest.py   # re-extracts the graph + rebuilds the vector store
```

A real connector would call the tool's API instead of returning a fixed list;
everything downstream (graph extraction, provenance, retrieval) is agnostic to
where the documents came from.

## Out of scope (lives in the architecture slides)

This is a demo. Deliberately mocked or skipped: real OAuth / source connectors,
incremental sync and freshness, permission filtering, and any evaluation harness.
The connectors in `oasis/sources.py` return a fixed in-memory corpus with
provenance metadata, standing in for real API-backed integrations.

## How the honest comparison works

Both panels call the same `get_llm()` instance with the same `build_prompt()`
template. The graph and vector stores are kept **separate** (Neo4j vs. Chroma)
so the baseline is genuinely "just a vector DB." Only retrieval differs.
