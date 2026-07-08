"""Build the Oasis knowledge graph (and, after Task 8, the vector baseline)."""
from langchain_experimental.graph_transformers import LLMGraphTransformer

from oasis.config import load_settings
from oasis.embeddings import get_embedder
from oasis.graph_store import GraphStore
from oasis.llm import get_llm
from oasis.sources import load_source_documents

ALLOWED_NODES = ["Service", "Incident", "Decision", "CodeComponent", "Team", "Person"]
ALLOWED_RELS = ["ADDRESSED_BY", "LED_TO", "IMPLEMENTED_BY", "OWNED_BY", "ON_CALL", "PART_OF"]


def main() -> None:
    settings = load_settings()
    docs = load_source_documents()

    print("=" * 60)
    print("OASIS INGEST — resolution log")
    print("=" * 60)

    llm = get_llm(settings)
    transformer = LLMGraphTransformer(
        llm=llm,
        allowed_nodes=ALLOWED_NODES,
        allowed_relationships=ALLOWED_RELS,
    )
    graph_docs = transformer.convert_to_graph_documents(docs)

    for src, gd in zip(docs, graph_docs):
        m = src.metadata
        print(f"\n[{m['source_tool']}] {m['source_id']} — {m['source_title']}")
        print(f"  url: {m['source_url']}")
        print(f"  nodes: {[n.id for n in gd.nodes]}")
        print(f"  rels:  {[(r.source.id, r.type, r.target.id) for r in gd.relationships]}")

    gs = GraphStore(settings)
    print("\nClearing existing graph (ingest rebuilds it from scratch)...")
    gs.clear()
    counts = gs.ingest_graph_documents(graph_docs)
    print("\n" + "-" * 60)
    print(f"Graph written: {counts['nodes']} nodes, {counts['relationships']} relationships")
    print("-" * 60)

    embedder = get_embedder()
    gs.add_node_embeddings(embedder)
    gs.ensure_vector_index()
    print("Entry-point embeddings + vector index ready.")

    from oasis.vector_rag import build_vector_store
    build_vector_store(settings, embedder, docs)
    print(f"Vector baseline (Chroma) written to {settings.chroma_dir}")


if __name__ == "__main__":
    main()
