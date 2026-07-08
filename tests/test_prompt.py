from oasis.generate import build_prompt


def test_prompt_includes_question_and_context_and_citation_instruction():
    p = build_prompt("Why retry 3 times?", "FACTS HERE")
    assert "Why retry 3 times?" in p
    assert "FACTS HERE" in p
    assert "cite" in p.lower()


def test_prompt_includes_history_when_provided():
    history = "user: hi\nassistant: hello"
    p = build_prompt("What is the retry count?", "FACTS HERE", history=history)
    # History text appears in the prompt
    assert "user: hi" in p
    assert "assistant: hello" in p
    # Conversation section header appears
    assert "Conversation so far:" in p
    # Question, context, and citation instruction still present
    assert "What is the retry count?" in p
    assert "FACTS HERE" in p
    assert "cite" in p.lower()


def test_prompt_no_history_section_when_empty():
    p = build_prompt("Why retry 3 times?", "FACTS HERE", history="")
    assert "Conversation so far:" not in p
