"""
Embedding module - supports OpenAI and local embeddings
"""
import os
from typing import List, Union, Optional
from abc import ABC, abstractmethod

import numpy as np
import tiktoken
from openai import OpenAI


class BaseEmbedder(ABC):
    """Base class for embedders"""
    
    @abstractmethod
    def embed(self, texts: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        """Generate embeddings for text(s)"""
        pass
    
    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        pass


class OpenAIEmbedder(BaseEmbedder):
    """OpenAI embedding provider"""
    
    def __init__(self, model: str = "text-embedding-3-small", api_key: Optional[str] = None):
        self.model = model
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        
        # Initialize tokenizer
        try:
            self.tokenizer = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fallback to cl100k_base for newer models
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
    
    def embed(self, texts: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        """Generate embeddings using OpenAI API"""
        is_single = isinstance(texts, str)
        if is_single:
            texts = [texts]
        
        response = self.client.embeddings.create(
            input=texts,
            model=self.model
        )
        
        embeddings = [item.embedding for item in response.data]
        
        return embeddings[0] if is_single else embeddings
    
    def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken"""
        return len(self.tokenizer.encode(text))
    
    def embed_batch(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """Embed texts in batches"""
        embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = self.embed(batch)
            embeddings.extend(batch_embeddings)
        
        return embeddings


class LocalEmbedder(BaseEmbedder):
    """Local embedding using sentence-transformers"""
    
    def __init__(self, model: str = "all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )
        
        self.model = SentenceTransformer(model)
        self.tokenizer = tiktoken.get_encoding("cl100k_base")  # Approximate
    
    def embed(self, texts: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        """Generate embeddings using local model"""
        is_single = isinstance(texts, str)
        if is_single:
            texts = [texts]
        
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        embeddings = embeddings.tolist()
        
        return embeddings[0] if is_single else embeddings
    
    def count_tokens(self, text: str) -> int:
        """Approximate token count"""
        return len(self.tokenizer.encode(text))
    
    def embed_batch(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """Embed texts in batches"""
        embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = self.embed(batch)
            embeddings.extend(batch_embeddings)
        
        return embeddings


def get_embedder(provider: str = "openai", model: str = None, **kwargs) -> BaseEmbedder:
    """
    Factory function to get embedder instance
    
    Args:
        provider: 'openai' or 'local'
        model: Model name (optional, uses defaults)
        **kwargs: Additional arguments for embedder
        
    Returns:
        Embedder instance
    """
    if provider == "openai":
        model = model or "text-embedding-3-small"
        return OpenAIEmbedder(model=model, **kwargs)
    elif provider == "local":
        model = model or "all-MiniLM-L6-v2"
        return LocalEmbedder(model=model)
    else:
        raise ValueError(f"Unknown embedding provider: {provider}")
