"""
LLM interface for RAG augmentation with citations
"""
import os
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod

from openai import OpenAI

from retriever import RetrievalResult


class BaseLLM(ABC):
    """Base class for LLM providers"""
    
    @abstractmethod
    def generate(self, 
                query: str, 
                contexts: List[str],
                include_citations: bool = True) -> Dict[str, Any]:
        """Generate answer with citations"""
        pass


class OpenAILLM(BaseLLM):
    """OpenAI LLM provider"""
    
    def __init__(self, 
                 model: str = "gpt-4o-mini",
                 temperature: float = 0.1,
                 max_tokens: int = 4000,
                 api_key: Optional[str] = None):
        """
        Initialize OpenAI LLM
        
        Args:
            model: Model name
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            api_key: OpenAI API key
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
    
    def generate(self,
                query: str,
                contexts: List[str],
                citations: List[Dict[str, Any]],
                include_citations: bool = True) -> Dict[str, Any]:
        """
        Generate answer using OpenAI API
        
        Args:
            query: User query
            contexts: List of context strings
            citations: Citation metadata
            include_citations: Whether to include citations in response
            
        Returns:
            Dictionary with answer and metadata
        """
        # Build context string with citations
        context_parts = []
        for i, (ctx, cit) in enumerate(zip(contexts, citations), 1):
            source_info = self._format_citation(cit)
            context_parts.append(f"[Source {i}: {source_info}]\n{ctx}")
        
        full_context = "\n\n---\n\n".join(context_parts)
        
        # Create system message
        system_msg = """You are a helpful assistant that answers questions based on provided context.

IMPORTANT INSTRUCTIONS:
1. Answer the question using ONLY information from the provided context
2. If the context doesn't contain enough information, say so clearly
3. Be concise but comprehensive
4. When making claims, reference the source number (e.g., "According to Source 1...")
5. If information comes from multiple sources, cite all relevant sources
6. Do not make up information not present in the context"""

        if not include_citations:
            system_msg += "\n7. Provide the answer without source citations in the final response"
        
        # Create user message
        user_msg = f"""Context:
{full_context}

Question: {query}

Please provide a comprehensive answer based on the context above."""

        # Call OpenAI API
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        
        answer = response.choices[0].message.content
        
        return {
            'answer': answer,
            'model': self.model,
            'usage': {
                'prompt_tokens': response.usage.prompt_tokens,
                'completion_tokens': response.usage.completion_tokens,
                'total_tokens': response.usage.total_tokens
            }
        }
    
    def _format_citation(self, citation: Dict[str, Any]) -> str:
        """Format citation for display"""
        doc_id = citation['doc_id']
        
        if 'pages' in citation:
            return f"{doc_id}, pages {citation['page_range']}"
        else:
            return f"{doc_id}, sections {citation['section_range']}"


class RAGAugmenter:
    """RAG system with LLM augmentation"""
    
    def __init__(self, llm: BaseLLM, include_citations: bool = True):
        """
        Initialize RAG augmenter
        
        Args:
            llm: LLM instance
            include_citations: Include source citations in answer
        """
        self.llm = llm
        self.include_citations = include_citations
    
    def augment(self, retrieval_result: RetrievalResult, verbose: bool = False) -> Dict[str, Any]:
        """
        Augment query with LLM using retrieved contexts
        
        Args:
            retrieval_result: Result from context retriever
            verbose: Print debug information
            
        Returns:
            Dictionary with answer and metadata
        """
        if not retrieval_result.contexts:
            return {
                'answer': "No relevant context found to answer the query.",
                'sources': [],
                'total_tokens': 0
            }
        
        # Extract contexts and citations
        contexts = [ctx.context_text for ctx in retrieval_result.contexts]
        citations = retrieval_result.citations
        
        if verbose:
            print(f"\n🤖 Generating answer using {len(contexts)} contexts...")
            print(f"📊 Total context tokens: {retrieval_result.total_tokens:,}")
        
        # Generate answer
        result = self.llm.generate(
            query=retrieval_result.query,
            contexts=contexts,
            citations=citations,
            include_citations=self.include_citations
        )
        
        # Add sources and metadata
        result['sources'] = citations
        result['num_sources'] = len(citations)
        result['context_tokens'] = retrieval_result.total_tokens
        
        if verbose:
            print(f"✅ Generated answer ({result['usage']['completion_tokens']} tokens)")
        
        return result


def get_llm(provider: str = "openai", 
            model: str = None,
            **kwargs) -> BaseLLM:
    """
    Factory function to get LLM instance
    
    Args:
        provider: 'openai' or 'local'
        model: Model name
        **kwargs: Additional arguments for LLM
        
    Returns:
        LLM instance
    """
    if provider == "openai":
        model = model or "gpt-4o-mini"
        return OpenAILLM(model=model, **kwargs)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
