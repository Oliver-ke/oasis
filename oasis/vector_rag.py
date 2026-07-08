from langchain_chroma import Chroma

from oasis.graph_rag import RetrievalResult

_COLLECTION = "oasis_baseline"


def build_vector_store(settings, embedder, docs) -> None:
    store = Chroma(
        collection_name=_COLLECTION,
        embedding_function=embedder,
        persist_directory=settings.chroma_dir,
    )
    # Reset so re-ingest is idempotent.
    try:
        store.delete_collection()
    except Exception:
        pass
    Chroma.from_documents(
        documents=docs,
        embedding=embedder,
        collection_name=_COLLECTION,
        persist_directory=settings.chroma_dir,
    )


def vector_retrieve(settings, embedder, question: str, k: int = 3) -> RetrievalResult:
    store = Chroma(
        collection_name=_COLLECTION,
        embedding_function=embedder,
        persist_directory=settings.chroma_dir,
    )
    hits = store.similarity_search(question, k=k)
    citations, seen = [], set()
    chunks = []
    for d in hits:
        m = d.metadata
        chunks.append(f"[{m.get('source_tool')}] {d.page_content}")
        cid = m.get("source_id")
        if cid and cid not in seen:
            seen.add(cid)
            citations.append({
                "source_tool": m.get("source_tool"),
                "source_id": cid,
                "source_url": m.get("source_url"),
                "source_title": m.get("source_title"),
            })
    context = "Top matching document chunks:\n\n" + "\n\n".join(chunks)
    return RetrievalResult(context=context, citations=citations, triples=[])
