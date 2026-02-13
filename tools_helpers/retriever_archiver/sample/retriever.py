"""
Context-aware retriever with expansion, deduplication, and re-ranking
"""
from typing import List, Dict, Any, Tuple, Set
from dataclasses import dataclass, field
import numpy as np

from vector_store import VectorStore, SearchResult
from embedder import BaseEmbedder


@dataclass
class ExpandedContext:
    """Expanded context with matched chunk and surrounding content"""
    matched_chunk: SearchResult
    context_chunks: List[SearchResult]
    context_text: str
    total_tokens: int
    pages_used: List[int] = field(default_factory=list)
    sections_used: List[int] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalResult:
    """Final retrieval result with all contexts"""
    query: str
    contexts: List[ExpandedContext]
    total_tokens: int
    num_sources: int
    citations: List[Dict[str, Any]] = field(default_factory=list)


class ContextRetriever:
    """Context-aware retriever with smart expansion"""
    
    def __init__(self,
                 vector_store: VectorStore,
                 embedder: BaseEmbedder,
                 top_k: int = 3,
                 context_window: int = 2,
                 adaptive_context: bool = True,
                 max_context_tokens: int = 32000,
                 deduplicate_overlaps: bool = True,
                 re_rank_context: bool = True,
                 similarity_threshold: float = 0.7):
        """
        Initialize context retriever
        
        Args:
            vector_store: Vector store instance
            embedder: Embedder instance
            top_k: Number of initial matches to retrieve
            context_window: Number of pages/sections before and after
            adaptive_context: Adjust window based on chunk size
            max_context_tokens: Maximum total tokens in context
            deduplicate_overlaps: Remove overlapping content
            re_rank_context: Re-rank expanded chunks by relevance
            similarity_threshold: Minimum similarity score to include
        """
        self.vector_store = vector_store
        self.embedder = embedder
        self.top_k = top_k
        self.context_window = context_window
        self.adaptive_context = adaptive_context
        self.max_context_tokens = max_context_tokens
        self.deduplicate_overlaps = deduplicate_overlaps
        self.re_rank_context = re_rank_context
        self.similarity_threshold = similarity_threshold
    
    def retrieve(self, query: str, verbose: bool = False) -> RetrievalResult:
        """
        Retrieve with context expansion
        
        Args:
            query: Search query
            verbose: Print debug information
            
        Returns:
            RetrievalResult with expanded contexts
        """
        # Step 1: Generate query embedding
        query_embedding = self.embedder.embed(query)
        
        # Step 2: Semantic search for top matches
        matches = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=self.top_k
        )
        
        # Filter by similarity threshold
        matches = [m for m in matches if m.score >= self.similarity_threshold]
        
        if verbose:
            print(f"\n🔍 Found {len(matches)} matches above threshold {self.similarity_threshold}")
            for i, match in enumerate(matches, 1):
                print(f"  {i}. Score: {match.score:.3f} | {match.metadata.get('doc_id', 'unknown')}")
        
        # Step 3: Expand context for each match
        expanded_contexts = []
        total_tokens = 0
        
        for match in matches:
            # Determine adaptive context window
            window = self._get_adaptive_window(match) if self.adaptive_context else self.context_window
            
            # Expand context
            expanded = self._expand_context(match, window, verbose=verbose)
            
            # Check token limit
            if total_tokens + expanded.total_tokens > self.max_context_tokens:
                if verbose:
                    print(f"⚠️  Token limit reached ({self.max_context_tokens}), truncating results")
                break
            
            expanded_contexts.append(expanded)
            total_tokens += expanded.total_tokens
        
        # Step 4: Deduplicate overlapping contexts
        if self.deduplicate_overlaps:
            expanded_contexts = self._deduplicate_contexts(expanded_contexts, verbose=verbose)
            # Recalculate total tokens
            total_tokens = sum(ctx.total_tokens for ctx in expanded_contexts)
        
        # Step 5: Re-rank contexts
        if self.re_rank_context and len(expanded_contexts) > 1:
            expanded_contexts = self._re_rank_contexts(query_embedding, expanded_contexts, verbose=verbose)
        
        # Step 6: Generate citations
        citations = self._generate_citations(expanded_contexts)
        
        if verbose:
            print(f"\n✅ Retrieved {len(expanded_contexts)} expanded contexts")
            print(f"📊 Total tokens: {total_tokens:,}")
            print(f"📚 Unique sources: {len(citations)}")
        
        return RetrievalResult(
            query=query,
            contexts=expanded_contexts,
            total_tokens=total_tokens,
            num_sources=len(citations),
            citations=citations
        )
    
    def _get_adaptive_window(self, match: SearchResult) -> int:
        """
        Adaptively determine context window based on chunk size
        
        Args:
            match: Search result
            
        Returns:
            Adjusted context window
        """
        chunk_tokens = self.embedder.count_tokens(match.content)
        
        if chunk_tokens < 200:
            return min(self.context_window + 1, 4)  # Expand more for small chunks
        elif chunk_tokens > 800:
            return max(self.context_window - 1, 1)  # Expand less for large chunks
        else:
            return self.context_window
    
    def _expand_context(self, 
                       match: SearchResult, 
                       window: int,
                       verbose: bool = False) -> ExpandedContext:
        """
        Expand context around a matched chunk
        
        Args:
            match: Matched search result
            window: Context window size
            verbose: Print debug info
            
        Returns:
            ExpandedContext
        """
        doc_id = match.metadata.get('doc_id')
        is_paginated = match.metadata.get('is_paginated', False)
        
        context_chunks = []
        
        if is_paginated:
            # Paginated document - expand by pages
            page_num = int(match.metadata.get('page_num', 1))
            total_pages = int(match.metadata.get('total_pages', page_num))
            
            # Calculate page range with boundary checks
            start_page = max(1, page_num - window)
            end_page = min(total_pages, page_num + window)
            
            if verbose:
                print(f"  📄 Expanding pages {start_page}-{end_page} (center: {page_num})")
            
            # Retrieve pages in range
            context_chunks = self.vector_store.get_page_range(doc_id, start_page, end_page)
            pages_used = list(range(start_page, end_page + 1))
            sections_used = []
            
        else:
            # Pageless document - expand by sections
            section_id = int(match.metadata.get('section_id', 0))
            
            # Get total sections by querying all chunks for this doc
            all_chunks_meta = self.vector_store.get_all_metadata(doc_id)
            total_sections = max([int(m[0].get('section_id', 0)) for m in all_chunks_meta]) + 1
            
            # Calculate section range
            start_section = max(0, section_id - window)
            end_section = min(total_sections - 1, section_id + window)
            
            if verbose:
                print(f"  📑 Expanding sections {start_section}-{end_section} (center: {section_id})")
            
            # Retrieve sections in range
            context_chunks = self.vector_store.get_section_range(doc_id, start_section, end_section)
            sections_used = list(range(start_section, end_section + 1))
            pages_used = []
        
        # Combine context text
        context_text = "\n\n".join([chunk.content for chunk in context_chunks])
        total_tokens = self.embedder.count_tokens(context_text)
        
        return ExpandedContext(
            matched_chunk=match,
            context_chunks=context_chunks,
            context_text=context_text,
            total_tokens=total_tokens,
            pages_used=pages_used,
            sections_used=sections_used,
            metadata={
                'doc_id': doc_id,
                'is_paginated': is_paginated,
                'match_score': match.score
            }
        )
    
    def _deduplicate_contexts(self, 
                             contexts: List[ExpandedContext],
                             verbose: bool = False) -> List[ExpandedContext]:
        """
        Deduplicate overlapping contexts
        
        Args:
            contexts: List of expanded contexts
            verbose: Print debug info
            
        Returns:
            Deduplicated contexts
        """
        if not contexts:
            return contexts
        
        # Group by document
        doc_groups: Dict[str, List[ExpandedContext]] = {}
        for ctx in contexts:
            doc_id = ctx.metadata['doc_id']
            if doc_id not in doc_groups:
                doc_groups[doc_id] = []
            doc_groups[doc_id].append(ctx)
        
        deduplicated = []
        
        for doc_id, doc_contexts in doc_groups.items():
            is_paginated = doc_contexts[0].metadata['is_paginated']
            
            if is_paginated:
                # Merge overlapping page ranges
                deduplicated.extend(self._merge_page_contexts(doc_contexts, verbose))
            else:
                # Merge overlapping section ranges
                deduplicated.extend(self._merge_section_contexts(doc_contexts, verbose))
        
        return deduplicated
    
    def _merge_page_contexts(self, 
                            contexts: List[ExpandedContext],
                            verbose: bool = False) -> List[ExpandedContext]:
        """Merge contexts with overlapping page ranges"""
        if len(contexts) == 1:
            return contexts
        
        # Sort by first page
        contexts = sorted(contexts, key=lambda x: min(x.pages_used))
        
        merged = []
        current = contexts[0]
        current_pages = set(current.pages_used)
        
        for next_ctx in contexts[1:]:
            next_pages = set(next_ctx.pages_used)
            
            # Check for overlap
            if current_pages & next_pages:  # Overlapping
                # Merge the contexts
                all_pages = sorted(current_pages | next_pages)
                doc_id = current.metadata['doc_id']
                
                # Retrieve merged page range
                merged_chunks = self.vector_store.get_page_range(
                    doc_id, min(all_pages), max(all_pages)
                )
                
                context_text = "\n\n".join([chunk.content for chunk in merged_chunks])
                total_tokens = self.embedder.count_tokens(context_text)
                
                # Keep the higher scoring match as primary
                matched_chunk = (current.matched_chunk if current.matched_chunk.score >= next_ctx.matched_chunk.score 
                               else next_ctx.matched_chunk)
                
                current = ExpandedContext(
                    matched_chunk=matched_chunk,
                    context_chunks=merged_chunks,
                    context_text=context_text,
                    total_tokens=total_tokens,
                    pages_used=all_pages,
                    sections_used=[],
                    metadata=current.metadata
                )
                current_pages = set(all_pages)
                
                if verbose:
                    print(f"  🔗 Merged overlapping pages: {all_pages}")
            else:
                # No overlap, save current and move to next
                merged.append(current)
                current = next_ctx
                current_pages = next_pages
        
        # Add last context
        merged.append(current)
        
        return merged
    
    def _merge_section_contexts(self,
                               contexts: List[ExpandedContext],
                               verbose: bool = False) -> List[ExpandedContext]:
        """Merge contexts with overlapping section ranges"""
        # Similar logic to page merging but for sections
        if len(contexts) == 1:
            return contexts
        
        contexts = sorted(contexts, key=lambda x: min(x.sections_used))
        
        merged = []
        current = contexts[0]
        current_sections = set(current.sections_used)
        
        for next_ctx in contexts[1:]:
            next_sections = set(next_ctx.sections_used)
            
            if current_sections & next_sections:
                all_sections = sorted(current_sections | next_sections)
                doc_id = current.metadata['doc_id']
                
                merged_chunks = self.vector_store.get_section_range(
                    doc_id, min(all_sections), max(all_sections)
                )
                
                context_text = "\n\n".join([chunk.content for chunk in merged_chunks])
                total_tokens = self.embedder.count_tokens(context_text)
                
                matched_chunk = (current.matched_chunk if current.matched_chunk.score >= next_ctx.matched_chunk.score
                               else next_ctx.matched_chunk)
                
                current = ExpandedContext(
                    matched_chunk=matched_chunk,
                    context_chunks=merged_chunks,
                    context_text=context_text,
                    total_tokens=total_tokens,
                    pages_used=[],
                    sections_used=all_sections,
                    metadata=current.metadata
                )
                current_sections = set(all_sections)
                
                if verbose:
                    print(f"  🔗 Merged overlapping sections: {all_sections}")
            else:
                merged.append(current)
                current = next_ctx
                current_sections = next_sections
        
        merged.append(current)
        return merged
    
    def _re_rank_contexts(self,
                         query_embedding: List[float],
                         contexts: List[ExpandedContext],
                         verbose: bool = False) -> List[ExpandedContext]:
        """
        Re-rank contexts by relevance
        
        Args:
            query_embedding: Query embedding
            contexts: List of contexts to re-rank
            verbose: Print debug info
            
        Returns:
            Re-ranked contexts
        """
        # Calculate relevance scores for each context chunk
        scored_contexts = []
        
        for ctx in contexts:
            # Embed the full context
            context_embedding = self.embedder.embed(ctx.context_text)
            
            # Calculate cosine similarity
            similarity = np.dot(query_embedding, context_embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(context_embedding)
            )
            
            scored_contexts.append((similarity, ctx))
        
        # Sort by similarity (descending)
        scored_contexts.sort(key=lambda x: x[0], reverse=True)
        
        if verbose:
            print("\n  📊 Re-ranked contexts:")
            for i, (score, ctx) in enumerate(scored_contexts, 1):
                doc_id = ctx.metadata['doc_id']
                location = f"pages {ctx.pages_used}" if ctx.pages_used else f"sections {ctx.sections_used}"
                print(f"    {i}. {doc_id} ({location}) - Relevance: {score:.3f}")
        
        return [ctx for _, ctx in scored_contexts]
    
    def _generate_citations(self, contexts: List[ExpandedContext]) -> List[Dict[str, Any]]:
        """
        Generate citations from contexts
        
        Args:
            contexts: List of expanded contexts
            
        Returns:
            List of citation dictionaries
        """
        citations = []
        
        for i, ctx in enumerate(contexts, 1):
            citation = {
                'source_id': i,
                'doc_id': ctx.metadata['doc_id'],
                'match_score': ctx.matched_chunk.score,
                'relevance': ctx.metadata.get('relevance_score', ctx.matched_chunk.score),
                'type': 'paginated' if ctx.pages_used else 'sectioned',
            }
            
            if ctx.pages_used:
                citation['pages'] = ctx.pages_used
                citation['page_range'] = f"{min(ctx.pages_used)}-{max(ctx.pages_used)}"
            else:
                citation['sections'] = ctx.sections_used
                citation['section_range'] = f"{min(ctx.sections_used)}-{max(ctx.sections_used)}"
            
            citations.append(citation)
        
        return citations
