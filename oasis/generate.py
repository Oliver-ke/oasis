from oasis.graph_rag import RetrievalResult

_TEMPLATE = """You are a company knowledge assistant. Answer the employee's \
question using ONLY the context below. Be specific and concise. Cite the \
sources you used inline by their tool and id (e.g. [Confluence ADR-014]). If \
the context is insufficient to fully answer, say what is missing.
{history_section}
Question:
{question}

Context:
{context}

Answer:"""


def build_prompt(question: str, context: str, history: str = "") -> str:
    if history:
        history_section = f"\nConversation so far:\n{history}\n"
    else:
        history_section = ""
    return _TEMPLATE.format(
        question=question,
        context=context,
        history_section=history_section,
    )


def answer(llm, question: str, retrieval: RetrievalResult, history: str = "") -> str:
    prompt = build_prompt(question, retrieval.context, history)
    return llm.invoke(prompt).content
