from dataclasses import dataclass, field


@dataclass
class RetrievalResult:
    context: str
    citations: list[dict] = field(default_factory=list)
    triples: list[tuple[str, str, str]] = field(default_factory=list)
    node_types: dict = field(default_factory=dict)


def assemble_context(rel_rows: list[dict], chunk_rows: list[dict] | None = None) -> RetrievalResult:
    """Pure assembly of traversed relationships + source chunk texts into
    prompt context + deduped citations + triples. No I/O. Follows Neo4j's
    recommended pattern: include BOTH chunk texts and entity-relationship
    pairs. Citations are merged and deduped across both inputs."""
    chunk_rows = chunk_rows or []
    triples: list[tuple[str, str, str]] = []
    seen_triple = set()
    citations: list[dict] = []
    seen_cite = set()

    def _cite(row: dict) -> None:
        cid = row.get("source_id")
        if cid and cid not in seen_cite:
            seen_cite.add(cid)
            citations.append({
                "source_tool": row.get("source_tool"),
                "source_id": cid,
                "source_url": row.get("source_url"),
                "source_title": row.get("source_title"),
            })

    for r in rel_rows:
        triple = (r["src"], r["type"], r["tgt"])
        if triple not in seen_triple:
            seen_triple.add(triple)
            triples.append(triple)
        _cite(r)

    excerpts: list[str] = []
    for c in chunk_rows:
        _cite(c)
        if c.get("text"):
            excerpts.append(f"[{c.get('source_tool')}] {c['text']}")

    fact_lines = [f"- {s} --[{t}]--> {o}" for (s, t, o) in triples]
    cite_lines = [
        f"- [{c['source_tool']}] {c['source_title']} ({c['source_url']})"
        for c in citations
    ]
    # Only include a section when it has content, so an empty excerpts/facts/
    # sources list never leaves a dangling header in the LLM prompt.
    sections: list[str] = []
    if excerpts:
        sections.append(
            "Source excerpts (gathered by traversing the graph):\n"
            + "\n\n".join(excerpts)
        )
    if fact_lines:
        sections.append(
            "Knowledge-graph facts (subject -> relation -> object):\n"
            + "\n".join(fact_lines)
        )
    if cite_lines:
        sections.append("Sources:\n" + "\n".join(cite_lines))
    context = "\n\n".join(sections) if sections else "No supporting context found."
    return RetrievalResult(context=context, citations=citations, triples=triples)


def graph_retrieve(gs, embedder, question: str, k: int = 4, max_hops: int = 2) -> RetrievalResult:
    q_vec = embedder.embed_query(question)
    hits = gs.entry_point_search(q_vec, k=k)
    seed_ids = [h["id"] for h in hits]
    if not seed_ids:
        return RetrievalResult(context="No graph entry points found.", citations=[], triples=[])
    rel_rows = gs.traverse(seed_ids, max_hops=max_hops)
    entity_ids = set(seed_ids)
    for r in rel_rows:
        entity_ids.add(r["src"])
        entity_ids.add(r["tgt"])
    chunk_rows = gs.collect_chunks(list(entity_ids))
    result = assemble_context(rel_rows, chunk_rows)
    names = {s for s, _, _ in result.triples} | {o for _, _, o in result.triples}
    result.node_types = gs.node_types(list(names))
    return result
