from oasis.config import load_settings


def test_defaults_when_env_absent(monkeypatch):
    for k in ["GEN_PROVIDER", "GEN_MODEL", "NEO4J_URI", "NEO4J_USER",
              "NEO4J_PASSWORD", "CHROMA_DIR", "ENABLE_GRAPH_VIZ"]:
        monkeypatch.delenv(k, raising=False)
    s = load_settings()
    assert s.gen_provider == "anthropic"
    assert s.neo4j_uri == "bolt://localhost:7687"
    assert s.chroma_dir == ".chroma"
    assert s.enable_graph_viz is False


def test_reads_env(monkeypatch):
    monkeypatch.setenv("GEN_PROVIDER", "openai")
    monkeypatch.setenv("GEN_MODEL", "gpt-4o")
    monkeypatch.setenv("ENABLE_GRAPH_VIZ", "true")
    s = load_settings()
    assert s.gen_provider == "openai"
    assert s.gen_model == "gpt-4o"
    assert s.enable_graph_viz is True
