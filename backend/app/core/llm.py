from langchain_community.llms import Ollama
from app.config.settings import settings
from langchain_core.language_models.llms import LLM

def get_llm() -> LLM:
    """
    Initializes and returns an Ollama LLM instance based on the application settings.
    """
    return Ollama(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        temperature=0.0  
    )