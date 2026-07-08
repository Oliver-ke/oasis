import streamlit as st

from oasis.config import load_settings
from oasis.embeddings import get_embedder
from oasis.llm import get_llm
from oasis.graph_store import GraphStore
from oasis.graph_rag import graph_retrieve
from oasis.vector_rag import vector_retrieve
from oasis.generate import answer

st.set_page_config(page_title="Oasis — knowledge graph chat", layout="wide")

DEMO_QUESTION = "Why does the auth service retry three times, and who owns that decision?"


@st.cache_resource
def _bootstrap():
    settings = load_settings()
    return settings, get_embedder(), get_llm(settings), GraphStore(settings)


def _render_citations(citations):
    st.markdown("**Sources**")
    if not citations:
        st.caption("No sources cited.")
        return
    for c in citations:
        st.markdown(
            f"- **[{c['source_tool']}]** [{c['source_title']}]({c['source_url']}) · `{c['source_id']}`"
        )


def _render_turn(turn, settings):
    """Render a single stored turn dict without any LLM recomputation."""
    with st.chat_message("user"):
        st.markdown(turn["question"])

    with st.chat_message("assistant"):
        st.markdown(turn["g_answer"])

        tools = sorted({c["source_tool"] for c in turn["g_citations"]})
        st.success(f"Assembled from {len(tools)} source tools: {', '.join(tools)}")

        _render_citations(turn["g_citations"])

        if settings.enable_graph_viz and turn["g_triples"]:
            from oasis.viz import render_subgraph
            st.markdown("**Traversed subgraph**")
            render_subgraph(turn["g_triples"], turn.get("g_node_types"))

        baseline = turn.get("baseline")
        if baseline is not None:
            with st.expander(f"Compare to plain vector search (k={baseline['k']})"):
                st.markdown(baseline["answer"])
                btools = sorted({c["source_tool"] for c in baseline["citations"]})
                st.info(f"{len(btools)} sources: {', '.join(btools) or 'none'}")
                _render_citations(baseline["citations"])
                st.caption(
                    "Same LLM, same prompt, same conversation — only retrieval differs."
                )


def main():
    settings, embedder, llm, gs = _bootstrap()

    st.title("Oasis")
    st.caption("Ask anything about the codebase. Follow-ups carry context.")

    # Sidebar controls
    st.sidebar.header("Options")
    compare = st.sidebar.toggle("Show vector-baseline comparison", value=False)
    k = st.sidebar.slider(
        "Baseline top-k",
        min_value=1,
        max_value=5,
        value=3,
        help="How many chunks the plain vector baseline retrieves.",
    )
    if st.sidebar.button("Clear chat"):
        st.session_state["messages"] = []
        st.rerun()

    if compare:
        st.sidebar.caption(
            "Baseline comparison is ON. New turns will include a vector-search expander. "
            "Prior turns without a baseline won't be updated retroactively."
        )

    # Initialise transcript
    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    messages: list[dict] = st.session_state["messages"]

    # Render existing transcript (no recomputation)
    for turn in messages:
        _render_turn(turn, settings)

    # Hint so users know they can try the demo question
    if not messages:
        st.caption(f"Try asking: *{DEMO_QUESTION}*")

    # New input
    prompt = st.chat_input(placeholder=DEMO_QUESTION)

    if prompt:
        # --- Build context-aware retrieval query ---
        if messages:
            prev_question = messages[-1]["question"]
            retrieval_query = prev_question + " " + prompt
        else:
            retrieval_query = prompt

        # --- Build history text from prior turns ---
        history_parts = []
        for t in messages:
            history_parts.append(f"User: {t['question']}\nAssistant: {t['g_answer']}")
        history = "\n\n".join(history_parts)

        # --- GraphRAG retrieval + answer ---
        with st.spinner("Assembling from the knowledge graph..."):
            g = graph_retrieve(gs, embedder, retrieval_query)
            g_answer = answer(llm, prompt, g, history=history)

        # --- Optional vector baseline ---
        baseline = None
        if compare:
            with st.spinner("Running vector baseline..."):
                v = vector_retrieve(settings, embedder, retrieval_query, k=k)
                v_answer = answer(llm, prompt, v, history=history)
            baseline = {
                "answer": v_answer,
                "citations": v.citations,
                "k": k,
            }

        # --- Store and rerun ---
        messages.append({
            "question": prompt,
            "g_answer": g_answer,
            "g_citations": g.citations,
            "g_triples": g.triples,
            "g_node_types": g.node_types,
            "baseline": baseline,
        })
        st.rerun()


if __name__ == "__main__":
    main()
