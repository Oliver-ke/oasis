import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    gen_provider: str
    gen_model: str
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    chroma_dir: str
    enable_graph_viz: bool


def load_settings() -> Settings:
    return Settings(
        gen_provider=os.getenv("GEN_PROVIDER", "anthropic"),
        gen_model=os.getenv("GEN_MODEL", "claude-sonnet-4-6"),
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", "oasisdemo"),
        chroma_dir=os.getenv("CHROMA_DIR", ".chroma"),
        enable_graph_viz=_as_bool(os.getenv("ENABLE_GRAPH_VIZ"), False),
    )
