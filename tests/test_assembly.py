from oasis.graph_rag import assemble_context


def _row(src, typ, tgt, tool, sid, url, title):
    return {"src": src, "type": typ, "tgt": tgt, "source_tool": tool,
            "source_id": sid, "source_url": url, "source_title": title}


def test_assemble_dedups_citations_and_builds_triples():
    rows = [
        _row("Decision ADR-014", "ADDRESSED_BY", "Incident INC-231",
             "Confluence", "ADR-014", "u1", "ADR-014"),
        _row("Decision ADR-014", "IMPLEMENTED_BY", "auth_service/client.py",
             "Confluence", "ADR-014", "u1", "ADR-014"),
        _row("Auth Service", "OWNED_BY", "Platform Identity",
             "Notion", "team-page", "u2", "Team Page"),
    ]
    result = assemble_context(rows)
    tools = {c["source_tool"] for c in result.citations}
    assert tools == {"Confluence", "Notion"}
    assert len(result.citations) == 2  # deduped by source_id
    assert ("Auth Service", "OWNED_BY", "Platform Identity") in result.triples
    assert "ADR-014" in result.context


def test_assemble_includes_chunk_text_and_merges_citations():
    rels = [_row("Decision ADR-014", "ADDRESSED_BY", "Incident INC-231",
                 "Confluence", "ADR-014", "u1", "ADR-014")]
    chunks = [
        {"text": "Incident INC-231: token endpoint flapping.",
         "source_tool": "Linear", "source_id": "INC-231",
         "source_url": "u3", "source_title": "INC-231"},
    ]
    result = assemble_context(rels, chunks)
    tools = {c["source_tool"] for c in result.citations}
    assert tools == {"Confluence", "Linear"}  # citation merged from chunk row
    assert "token endpoint flapping" in result.context  # excerpt text included


def test_assemble_empty_inputs_produce_no_dangling_headers():
    result = assemble_context([], [])
    assert result.citations == []
    assert result.triples == []
    # No section headers when there is nothing to show.
    assert "Source excerpts" not in result.context
    assert "Knowledge-graph facts" not in result.context
    assert "Sources:" not in result.context
    assert result.context == "No supporting context found."


def test_assemble_facts_only_when_no_chunks():
    rels = [_row("A", "REL", "B", "Confluence", "ADR-014", "u1", "ADR-014")]
    result = assemble_context(rels, [])
    # Facts + Sources present, but no empty excerpts header.
    assert "Source excerpts" not in result.context
    assert "Knowledge-graph facts" in result.context
    assert "Sources:" in result.context
