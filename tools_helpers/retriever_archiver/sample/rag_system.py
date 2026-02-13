"""
Main Context-Aware RAG System
"""
from typing import List, Dict, Any, Optional
from pathlib import Path
from tqdm import tqdm

from config import RAGConfig, get_config
from document_processor import DocumentProcessor, Document
from embedder import get_embedder, BaseEmbedder
from vector_store import VectorStore
from retriever import ContextRetriever, RetrievalResult
from llm_interface import get_llm, RAGAugmenter


class ContextRAG:
    """Main Context-Aware RAG System"""
    
    def __init__(self, config: Optional[RAGConfig] = None):
        """
        Initialize RAG system
        
        Args:
            config: RAG configuration (uses defaults if None)
        """
        self.config = config or get_config()
        
        # Initialize components
        self.embedder: BaseEmbedder = get_embedder(
            provider=self.config.embedding.provider,
            model=self.config.embedding.model
        )
        
        self.vector_store = VectorStore(
            collection_name=self.config.vector_db.collection_name,
            persist_directory=self.config.vector_db.persist_directory
        )
        
        self.retriever = ContextRetriever(
            vector_store=self.vector_store,
            embedder=self.embedder,
            top_k=self.config.retrieval.top_k,
            context_window=self.config.retrieval.context_window,
            adaptive_context=self.config.retrieval.adaptive_context,
            max_context_tokens=self.config.retrieval.max_context_tokens,
            deduplicate_overlaps=self.config.retrieval.deduplicate_overlaps,
            re_rank_context=self.config.retrieval.re_rank_context,
            similarity_threshold=self.config.retrieval.similarity_threshold
        )
        
        llm = get_llm(
            provider=self.config.llm.provider,
            model=self.config.llm.model,
            temperature=self.config.llm.temperature,
            max_tokens=self.config.llm.max_tokens
        )
        
        self.augmenter = RAGAugmenter(
            llm=llm,
            include_citations=self.config.llm.include_citations
        )
        
        self.verbose = self.config.verbose
    
    def ingest_document(self, file_path: str) -> Dict[str, Any]:
        """
        Ingest a document into the RAG system
        
        Args:
            file_path: Path to document file
            
        Returns:
            Dictionary with ingestion statistics
        """
        if self.verbose:
            print(f"\n📄 Processing document: {file_path}")
        
        # Step 1: Process document
        doc = DocumentProcessor.process_document(file_path)
        
        if self.verbose:
            print(f"   Type: {doc.doc_type.value}")
            print(f"   Pages/Sections: {doc.total_pages}")
        
        # Step 2: Generate embeddings
        if self.verbose:
            print(f"   Generating embeddings...")
        
        texts = [page.content for page in doc.pages]
        embeddings = self.embedder.embed_batch(
            texts, 
            batch_size=self.config.embedding.batch_size
        )
        
        # Step 3: Prepare metadata
        metadatas = []
        ids = []
        
        for i, page in enumerate(doc.pages):
            metadata = {
                'doc_id': doc.doc_id,
                'doc_type': doc.doc_type.value,
                'file_path': doc.file_path,
                'total_pages': doc.total_pages,
                'is_paginated': doc.metadata.get('is_paginated', False),
            }
            
            # Add page-specific metadata
            if page.page_num is not None:
                metadata['page_num'] = page.page_num
            
            if page.metadata:
                metadata.update(page.metadata)
            
            metadatas.append(metadata)
            ids.append(f"{doc.doc_id}_chunk_{i}")
        
        # Step 4: Store in vector database
        if self.verbose:
            print(f"   Storing in vector database...")
        
        self.vector_store.add_documents(
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
        
        if self.verbose:
            print(f"✅ Ingested {len(texts)} chunks from {doc.doc_id}")
        
        return {
            'doc_id': doc.doc_id,
            'doc_type': doc.doc_type.value,
            'num_chunks': len(texts),
            'file_path': file_path
        }
    
    def ingest_documents(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """
        Ingest multiple documents
        
        Args:
            file_paths: List of file paths
            
        Returns:
            List of ingestion results
        """
        results = []
        
        iterator = tqdm(file_paths, desc="Ingesting documents") if self.verbose else file_paths
        
        for file_path in iterator:
            try:
                result = self.ingest_document(file_path)
                results.append(result)
            except Exception as e:
                print(f"❌ Error ingesting {file_path}: {e}")
                results.append({
                    'file_path': file_path,
                    'error': str(e)
                })
        
        return results
    
    def query(self, question: str, retrieve_only: bool = False) -> Dict[str, Any]:
        """
        Query the RAG system
        
        Args:
            question: User question
            retrieve_only: Only retrieve context, don't augment with LLM
            
        Returns:
            Dictionary with answer and metadata
        """
        if self.verbose:
            print(f"\n❓ Query: {question}")
        
        # Step 1: Retrieve with context expansion
        retrieval_result = self.retriever.retrieve(question, verbose=self.verbose)
        
        if retrieve_only:
            # Return just the retrieval results
            return {
                'query': question,
                'contexts': [
                    {
                        'text': ctx.context_text,
                        'tokens': ctx.total_tokens,
                        'pages': ctx.pages_used,
                        'sections': ctx.sections_used,
                        'metadata': ctx.metadata
                    }
                    for ctx in retrieval_result.contexts
                ],
                'citations': retrieval_result.citations,
                'total_tokens': retrieval_result.total_tokens
            }
        
        # Step 2: Augment with LLM
        result = self.augmenter.augment(retrieval_result, verbose=self.verbose)
        
        # Add query to result
        result['query'] = question
        
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the RAG system"""
        return {
            'total_chunks': self.vector_store.count(),
            'config': {
                'embedding_model': self.config.embedding.model,
                'llm_model': self.config.llm.model,
                'top_k': self.config.retrieval.top_k,
                'context_window': self.config.retrieval.context_window,
                'max_context_tokens': self.config.retrieval.max_context_tokens
            }
        }
    
    def clear_database(self):
        """Clear the vector database"""
        self.vector_store.delete_collection()
        
        # Recreate collection
        self.vector_store = VectorStore(
            collection_name=self.config.vector_db.collection_name,
            persist_directory=self.config.vector_db.persist_directory
        )
        
        if self.verbose:
            print("🗑️  Database cleared")
