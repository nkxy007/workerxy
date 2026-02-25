import pytest
import os
import creds
from utils.llm_provider import LLMFactory
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

# Set environment variables for tests to allow client initialization
os.environ["OPENAI_API_KEY"] = creds.OPENAI_KEY
os.environ["ANTHROPIC_API_KEY"] = creds.ANTHROPIC_KEY
os.environ["GOOGLE_API_KEY"] = creds.GEMINI_KEY
os.environ["XAI_API_KEY"] = creds.GROK_KEY
# Note: langchain_xai might be needed if testing xai specifically

def test_determine_provider():
    assert LLMFactory._determine_provider("gpt-4o") == "openai"
    assert LLMFactory._determine_provider("claude-3-sonnet") == "anthropic"
    assert LLMFactory._determine_provider("gemini-1.5-pro") == "google_genai"
    assert LLMFactory._determine_provider("google-search-model") == "google_genai"
    assert LLMFactory._determine_provider("grok-beta") == "xai"
    assert LLMFactory._determine_provider("unknown-model") == "openai"

def test_get_llm_routing():
    # We can test that it returns the right class (without necessarily calling the API)
    # However, init_chat_model returns a proxy or the actual class depending on version
    
    gpt_model = LLMFactory.get_llm("gpt-4o")
    assert isinstance(gpt_model, ChatOpenAI)
    
    claude_model = LLMFactory.get_llm("claude-3-opus-20240229")
    assert isinstance(claude_model, ChatAnthropic)

    gemini_model = LLMFactory.get_llm("gemini-1.5-flash")
    assert isinstance(gemini_model, ChatGoogleGenerativeAI)

def test_kwargs_stripping():
    # Check that OpenAI specific args don't crash Anthropic
    try:
        claude_model = LLMFactory.get_llm("claude-3-sonnet", use_responses_api=True, reasoning={"effort": "high"})
        assert isinstance(claude_model, ChatAnthropic)
    except Exception as e:
        pytest.fail(f"LLMFactory failed to strip OpenAI args for Anthropic: {e}")

def test_openai_with_responses():
    model = LLMFactory.get_llm("gpt-4o", use_responses_api=True)
    assert isinstance(model, ChatOpenAI)
    # We can't easily check internal state without deep inspection, but it shouldn't error

def test_get_embeddings_routing():
    # OpenAI
    openai_emb = LLMFactory.get_embeddings("text-embedding-3-small")
    assert isinstance(openai_emb, OpenAIEmbeddings)
    
    # Google
    google_emb = LLMFactory.get_embeddings("models/embedding-001")
    assert isinstance(google_emb, GoogleGenerativeAIEmbeddings)

    # Default fallback to OpenAI
    default_emb = LLMFactory.get_embeddings("unknown-prefix-model")
    assert isinstance(default_emb, OpenAIEmbeddings)
