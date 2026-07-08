from langchain_neo4j import Neo4jGraph

from oasis.config import Settings


class GraphStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.graph = Neo4jGraph(
            url=settings.neo4j_uri,
            username=settings.neo4j_user,
            password=settings.neo4j_password,
            refresh_schema=False,
        )

    def query(self, cypher: str, params: dict | None = None) -> list[dict]:
        return self.graph.query(cypher, params or {})

    def clear(self) -> None:
        self.query("MATCH (n) DETACH DELETE n")

    def ingest_graph_documents(self, graph_documents) -> dict:
        """Inject source provenance onto every node and relationship, then
        write the graph. Returns node/relationship counts.

        Uses langchain_neo4j's add_graph_documents with baseEntityLabel=True
        and include_source=True so that:
        - Every entity node gets the __Entity__ base label.
        - A (:Document)-[:MENTIONS]->(entity) edge is created per source,
          with the source text stored on the Document node.
        Requires APOC core plugin in the Neo4j container.

        Provenance note: entity nodes are MERGEd by id, so an entity that
        appears in several sources keeps the LAST writer's source_* values
        (last-write-wins). This is fine for retrieval/citations: those are
        driven by RELATIONSHIP provenance and by the per-source Document
        nodes (both single-source and accurate), never by shared-entity
        node provenance. Multi-valued node provenance is intentionally not
        modelled (unused by the demo).
        """
        for gd in graph_documents:
            meta = gd.source.metadata
            prov = {
                "source_tool": meta["source_tool"],
                "source_id": meta["source_id"],
                "source_url": meta["source_url"],
                "source_title": meta["source_title"],
            }
            for node in gd.nodes:
                node.properties.update(prov)
            for rel in gd.relationships:
                rel.properties.update(prov)

        self.graph.add_graph_documents(
            graph_documents, baseEntityLabel=True, include_source=True
        )

        counts = self.query(
            "MATCH (n) WITH count(n) AS nodes "
            "MATCH ()-[r]->() RETURN nodes, count(r) AS relationships"
        )
        return counts[0] if counts else {"nodes": 0, "relationships": 0}

    def add_node_embeddings(self, embedder) -> None:
        rows = self.query(
            "MATCH (n:__Entity__) "
            "RETURN elementId(n) AS eid, coalesce(n.id, '') AS name, "
            "coalesce(n.description, '') AS descr"
        )
        for r in rows:
            text = f"{r['name']}. {r['descr']}".strip()
            vec = embedder.embed_query(text)
            self.query(
                "MATCH (n) WHERE elementId(n) = $eid SET n.embedding = $vec",
                {"eid": r["eid"], "vec": vec},
            )

    def ensure_vector_index(self) -> None:
        self.query(
            "CREATE VECTOR INDEX oasis_entity_idx IF NOT EXISTS "
            "FOR (n:__Entity__) ON (n.embedding) "
            "OPTIONS {indexConfig: {`vector.dimensions`: 384, "
            "`vector.similarity_function`: 'cosine'}}"
        )

    def entry_point_search(self, query_embedding: list[float], k: int = 4) -> list[dict]:
        return self.query(
            "CALL db.index.vector.queryNodes('oasis_entity_idx', $k, $vec) "
            "YIELD node, score "
            "RETURN node.id AS id, labels(node) AS labels, score",
            {"k": k, "vec": query_embedding},
        )

    def traverse(self, seed_ids: list[str], max_hops: int = 2) -> list[dict]:
        hops = int(max_hops)
        # Return only entity->entity knowledge relationships. We exclude the
        # structural (:Document)-[:MENTIONS]->(:__Entity__) edges so the assembled
        # "facts" context (and the graph viz) stay clean of Document plumbing;
        # source text/citations come from collect_chunks() instead. NOTE: Neo4j
        # forbids relationship-type expressions in variable-length patterns
        # (no [r:!MENTIONS*1..n]), so we filter per-rel after UNWIND. At demo
        # scale the wider walk is negligible.
        return self.query(
            f"MATCH (s:__Entity__) WHERE s.id IN $seeds "
            f"MATCH (s)-[r*1..{hops}]-(:__Entity__) "
            "UNWIND r AS rel "
            "WITH DISTINCT rel "
            "WHERE type(rel) <> 'MENTIONS' "
            "AND startNode(rel):__Entity__ AND endNode(rel):__Entity__ "
            "RETURN startNode(rel).id AS src, type(rel) AS type, "
            "endNode(rel).id AS tgt, rel.source_tool AS source_tool, "
            "rel.source_id AS source_id, rel.source_url AS source_url, "
            "rel.source_title AS source_title",
            {"seeds": seed_ids},
        )

    def collect_chunks(self, entity_ids: list[str]) -> list[dict]:
        return self.query(
            "MATCH (d:Document)-[:MENTIONS]->(e:__Entity__) "
            "WHERE e.id IN $ids "
            "RETURN DISTINCT d.text AS text, d.source_tool AS source_tool, "
            "d.source_id AS source_id, d.source_url AS source_url, "
            "d.source_title AS source_title",
            {"ids": entity_ids},
        )

    def node_types(self, ids: list[str]) -> dict:
        """Map entity id -> its primary type label (e.g. Decision, Incident),
        used to colour the subgraph visualization by entity type."""
        if not ids:
            return {}
        rows = self.query(
            "MATCH (n:__Entity__) WHERE n.id IN $ids "
            "RETURN n.id AS id, "
            "head([l IN labels(n) WHERE l <> '__Entity__']) AS type",
            {"ids": ids},
        )
        return {r["id"]: (r["type"] or "Entity") for r in rows}
