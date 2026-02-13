"""
Configuration module for Context-Aware RAG system
"""
from typing import Literal
from pydantic import BaseModel, Field


class EmbeddingConfig(BaseModel):
    """Embedding configuration"""
    provider: Literal['openai', 'local'] = 'openai'
    model: str = 'text-embedding-3-small'
    local_model: str = 'all-MiniLM-L6-v2'  # for local embedding
    batch_size: int = 100
    

class ChunkingConfig(BaseModel):
    """Chunking strategy configuration"""
    pageless_strategy: Literal['hierarchical_semantic', 'fixed', 'sliding'] = 'hierarchical_semantic'
    markdown_split_by: str = 'headers'  # H1, H2, H3
    code_split_by: str = 'functions'  # or 'classes'
    chunk_size: int = 512  # tokens for fixed chunking
    chunk_overlap: int = 50  # tokens
    min_chunk_size: int = 50  # minimum chunk size in tokens
    

class RetrievalConfig(BaseModel):
    """Retrieval configuration"""
    top_k: int = 3
    context_window: int = 2  # ±N pages/sections
    adaptive_context: bool = True  # adjust based on chunk size
    max_context_tokens: int = 32000
    deduplicate_overlaps: bool = True
    re_rank_context: bool = True
    similarity_threshold: float = 0.7  # minimum similarity score
    

class LLMConfig(BaseModel):
    """LLM configuration"""
    provider: Literal['openai', 'local'] = 'openai'
    model: str = 'gpt-4o-mini'
    temperature: float = 0.1
    max_tokens: int = 4000
    include_citations: bool = True
    

class VectorDBConfig(BaseModel):
    """Vector database configuration"""
    provider: Literal['chromadb'] = 'chromadb'
    collection_name: str = 'documents'
    persist_directory: str = './chroma_db'
    

class RAGConfig(BaseModel):
    """Main RAG system configuration"""
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    vector_db: VectorDBConfig = Field(default_factory=VectorDBConfig)
    
    # Performance
    cache_embeddings: bool = True
    verbose: bool = True
    

# Default configuration instance
DEFAULT_CONFIG = RAGConfig()


def get_config(**kwargs) -> RAGConfig:
    """
    Get configuration with optional overrides
    
    Example:
        config = get_config(
            embedding={'provider': 'local'},
            retrieval={'top_k': 5}
        )
    """
    config_dict = DEFAULT_CONFIG.model_dump()
    
    # Update with provided kwargs
    for key, value in kwargs.items():
        if key in config_dict and isinstance(value, dict):
            config_dict[key].update(value)
        else:
            config_dict[key] = value
    
    return RAGConfig(**config_dict)
