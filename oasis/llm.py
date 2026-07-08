from langchain_core.language_models.chat_models import BaseChatModel

from oasis.config import Settings


def get_llm(settings: Settings) -> BaseChatModel:
    """Single swap point for the generation model. Both retrieval paths
    use the SAME instance so the comparison is honest."""
    if settings.gen_provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=settings.gen_model, temperature=0)
    if settings.gen_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=settings.gen_model, temperature=0)
    raise ValueError(f"Unknown GEN_PROVIDER: {settings.gen_provider!r}")
