import html

import streamlit as st

from oasis.config import load_settings
from oasis.embeddings import get_embedder
from oasis.generate import answer
from oasis.graph_rag import graph_retrieve
from oasis.graph_store import GraphStore
from oasis.llm import get_llm
from oasis.vector_rag import vector_retrieve

st.set_page_config(page_title="oasis · knowledge graph", layout="wide")

DEMO_QUESTION = (
    "Why does the auth service retry three times, and who owns that decision?"
)

# Terminal / phosphor theme. The dark base + monospace come from
# .streamlit/config.toml; this adds the accent + REPL polish on top.
_TERMINAL_CSS = """
<style>
:root {
  --oa-accent:#4AF6A0; --oa-dim:#6B7A72; --oa-border:#1E2A27; --oa-panel:#11201C;
}
.stApp { background:#0B0F0E; }
/* nicer monospace on text surfaces (icons are left untouched) */
[data-testid="stMarkdownContainer"],
textarea[data-testid="stChatInputTextArea"],
.stTextInput input {
  font-family:"JetBrains Mono","Cascadia Code","SFMono-Regular",Menlo,Consolas,monospace !important;
}
h1, h2, h3 { color:var(--oa-accent) !important; letter-spacing:.3px; }
[data-testid="stMarkdownContainer"] a { color:var(--oa-accent) !important; }
[data-testid="stMarkdownContainer"] code {
  color:var(--oa-accent) !important; background:var(--oa-panel) !important;
  padding:1px 5px; border-radius:4px;
}
/* chat input as a terminal field with a phosphor caret */
[data-testid="stChatInput"] { border:1px solid var(--oa-border); border-radius:6px; }
textarea[data-testid="stChatInputTextArea"] { color:#B7F5D2 !important; }
/* config popover trigger reads like a terminal button */
[data-testid="stPopover"] button {
  border:1px solid var(--oa-border) !important; color:var(--oa-accent) !important;
  background:var(--oa-panel) !important;
}
/* dim, monospace captions */
[data-testid="stCaptionContainer"] { color:var(--oa-dim) !important; }
/* hide chat avatars — the phosphor "&gt;" prompt marks the user line instead */
[data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessageAvatarAssistant"] { display:none !important; }
[data-testid="stChatMessage"] { background:transparent; padding-left:0; }
</style>
"""


def _inject_theme():
    st.markdown(_TERMINAL_CSS, unsafe_allow_html=True)


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
        st.markdown(
            f"<span style='color:#4AF6A0;font-weight:700'>&gt;</span> "
            f"{html.escape(turn['question'])}",
            unsafe_allow_html=True,
        )

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
    _inject_theme()

    # Header row: prompt-style title on the left, config dropdown on the right.
    head, cfg = st.columns([5, 1], vertical_alignment="bottom")
    with head:
        st.markdown("## OASIS")
        st.caption("Knowledge center for company information, connect to all sources")
    with cfg:
        with st.popover("config", use_container_width=True):
            compare = st.toggle("vector-baseline comparison", value=False)
            k = st.slider(
                "baseline top-k",
                min_value=1,
                max_value=5,
                value=3,
                help="How many chunks the plain vector baseline retrieves.",
            )
            if compare:
                st.caption(
                    "on — new answers get a vector-search expander; "
                    "earlier turns aren't backfilled."
                )
            if st.button("clear chat", use_container_width=True):
                st.session_state["messages"] = []
                st.rerun()

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
        messages.append(
            {
                "question": prompt,
                "g_answer": g_answer,
                "g_citations": g.citations,
                "g_triples": g.triples,
                "g_node_types": g.node_types,
                "baseline": baseline,
            }
        )
        st.rerun()


if __name__ == "__main__":
    main()
