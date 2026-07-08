import streamlit as st

# Entity type -> (fill, border, text). Rendered with native Graphviz (st.graphviz_chart),
# which does proper graph layout — no physics jitter, no overlap, and it scales to the
# container instead of clipping. Colour encodes entity type; the legend maps it.
_TYPE_COLORS = {
    "incident": ("#E0533D", "#B23A28", "white"),       # red — what went wrong
    "decision": ("#3D6FE0", "#2A52B0", "white"),       # blue — the choice made
    "codecomponent": ("#2FAE66", "#1F8A4F", "white"),  # green — where it lives
    "service": ("#8257E5", "#6238C0", "white"),        # purple — the system
    "team": ("#E0A53D", "#8A6216", "#1A1A1A"),         # amber — who owns it
    "person": ("#17A2B8", "#0E7C8C", "white"),         # teal — the human
}
_DEFAULT = ("#9AA0A6", "#6E747B", "white")


def _colors(t: str):
    return _TYPE_COLORS.get((t or "").lower(), _DEFAULT)


def _wrap(name: str, width: int = 14) -> str:
    """Wrap a long node label onto multiple lines (Graphviz \\n) so circles
    stay compact instead of ballooning to fit one long string."""
    words = name.replace("/", " / ").replace("_", " ").split()
    lines, cur = [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return "\\n".join(lines)


def render_subgraph(triples, node_types=None) -> None:
    """Render the traversed entity subgraph with native Graphviz: circular,
    colour-coded nodes and directed, labelled relationships, plus a legend
    mapping colour -> entity type. `node_types` maps entity id -> type label."""
    if not triples:
        st.caption("No subgraph to display.")
        return
    node_types = node_types or {}

    # Distinct nodes, in first-seen order.
    seen: list[str] = []
    for s, _, o in triples:
        for name in (s, o):
            if name not in seen:
                seen.append(name)

    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace('"', '\\"')

    dot = [
        "digraph oasis {",
        '  rankdir="LR";',
        '  bgcolor="transparent";',
        "  nodesep=0.5;",
        "  ranksep=0.9;",
        '  node [shape=circle, style="filled", fixedsize=false, '
        'fontname="Helvetica", fontsize=11, penwidth=2];',
        '  edge [color="#C2C7CE", fontname="Helvetica", fontsize=9, '
        'fontcolor="#8A8F97", arrowsize=0.75, penwidth=1.3];',
    ]
    for name in seen:
        fill, border, text = _colors(node_types.get(name, "Entity"))
        dot.append(
            f'  "{esc(name)}" [fillcolor="{fill}", color="{border}", '
            f'fontcolor="{text}", label="{_wrap(name)}"];'
        )
    for s, rel, o in triples:
        dot.append(
            f'  "{esc(s)}" -> "{esc(o)}" [label="{rel.replace("_", " ").lower()}"];'
        )
    dot.append("}")

    # Legend — only the entity types present in this subgraph.
    present: list[str] = []
    for name in seen:
        t = node_types.get(name, "Entity")
        if t not in present:
            present.append(t)
    legend = " &nbsp; ".join(
        f"<span style='color:{_colors(t)[0]};font-size:17px;vertical-align:middle'>&#9679;</span>"
        f"<span style='font-size:13px;color:#3c3c3c;vertical-align:middle'> {t}</span>"
        for t in sorted(present)
    )
    st.markdown(legend, unsafe_allow_html=True)
    st.graphviz_chart("\n".join(dot), use_container_width=True)
