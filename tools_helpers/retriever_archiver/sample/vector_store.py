"""
Vector store module using ChromaDB
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import chromadb
from chromadb.config import Settings


@dataclass
class SearchResult:
    """Search result with metadata"""
    content: str
    metadata: Dict[str, Any]
    score: float
    chunk_id: str


class VectorStore:
    """ChromaDB vector store wrapper"""
    
    def __init__(self, 
                 collection_name: str = "documents",
                 persist_directory: str = "./chroma_db"):
        """
        Initialize ChromaDB vector store
        
        Args:
            collection_name: Name of the collection
            persist_directory: Directory to persist the database
        """
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        
        self.collection_name = collection_name
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
    
    def add_documents(self,
                     documents: List[str],
                     embeddings: List[List[float]],
                     metadatas: List[Dict[str, Any]],
                     ids: Optional[List[str]] = None):
        """
        Add documents to the vector store
        
        Args:
            documents: List of document texts
            embeddings: List of embedding vectors
            metadatas: List of metadata dictionaries
            ids: Optional list of document IDs
        """
        if ids is None:
            ids = [f"doc_{i}" for i in range(len(documents))]
        
        # Ensure metadata values are serializable
        clean_metadatas = []
        for meta in metadatas:
            clean_meta = {}
            for key, value in meta.items():
                if value is None:
                    clean_meta[key] = "null"
                elif isinstance(value, (str, int, float, bool)):
                    clean_meta[key] = value
                else:
                    clean_meta[key] = str(value)
            clean_metadatas.append(clean_meta)
        
        self.collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=clean_metadatas,
            ids=ids
        )
    
    def search(self,
               query_embedding: List[float],
               top_k: int = 5,
               where: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        """
        Search for similar documents
        
        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            where: Metadata filter conditions
            
        Returns:
            List of SearchResult objects
        """
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where
        )
        
        search_results = []
        
        # ChromaDB returns lists of lists
        documents = results['documents'][0]
        metadatas = results['metadatas'][0]
        distances = results['distances'][0]
        ids = results['ids'][0]
        
        for doc, meta, dist, doc_id in zip(documents, metadatas, distances, ids):
            # Convert distance to similarity score (cosine similarity)
            # Distance is 1 - cosine_similarity for cosine space
            score = 1 - dist
            
            search_results.append(SearchResult(
                content=doc,
                metadata=meta,
                score=score,
                chunk_id=doc_id
            ))
        
        return search_results
    
    def get_by_ids(self, ids: List[str]) -> List[SearchResult]:
        """
        Get documents by their IDs
        
        Args:
            ids: List of document IDs
            
        Returns:
            List of SearchResult objects
        """
        results = self.collection.get(
            ids=ids,
            include=['documents', 'metadatas']
        )
        
        search_results = []
        
        for doc, meta, doc_id in zip(
            results['documents'],
            results['metadatas'],
            results['ids']
        ):
            search_results.append(SearchResult(
                content=doc,
                metadata=meta,
                score=1.0,  # Perfect match since we're getting by ID
                chunk_id=doc_id
            ))
        
        return search_results
    
    def delete_collection(self):
        """Delete the entire collection"""
        self.client.delete_collection(name=self.collection_name)
    
    def count(self) -> int:
        """Get total number of documents in collection"""
        return self.collection.count()
    
    def get_all_metadata(self, doc_id: str) -> List[Dict[str, Any]]:
        """
        Get all chunks metadata for a specific document
        
        Args:
            doc_id: Document ID
            
        Returns:
            List of metadata dictionaries
        """
        results = self.collection.get(
            where={"doc_id": doc_id},
            include=['metadatas', 'documents']
        )
        
        return list(zip(results['metadatas'], results['documents'], results['ids']))
    
    def get_page_range(self, 
                       doc_id: str, 
                       start_page: int, 
                       end_page: int) -> List[SearchResult]:
        """
        Get all chunks within a page range
        
        Args:
            doc_id: Document ID
            start_page: Starting page number
            end_page: Ending page number (inclusive)
            
        Returns:
            List of SearchResult objects
        """
        # Get all chunks for this document
        all_chunks = self.collection.get(
            where={"doc_id": doc_id},
            include=['metadatas', 'documents']
        )
        
        results = []
        for doc, meta, chunk_id in zip(
            all_chunks['documents'],
            all_chunks['metadatas'],
            all_chunks['ids']
        ):
            page_num = meta.get('page_num')
            if page_num and start_page <= int(page_num) <= end_page:
                results.append(SearchResult(
                    content=doc,
                    metadata=meta,
                    score=1.0,
                    chunk_id=chunk_id
                ))
        
        # Sort by page number
        results.sort(key=lambda x: int(x.metadata.get('page_num', 0)))
        return results
    
    def get_section_range(self,
                         doc_id: str,
                         start_section: int,
                         end_section: int) -> List[SearchResult]:
        """
        Get all chunks within a section range (for pageless docs)
        
        Args:
            doc_id: Document ID
            start_section: Starting section ID
            end_section: Ending section ID (inclusive)
            
        Returns:
            List of SearchResult objects
        """
        all_chunks = self.collection.get(
            where={"doc_id": doc_id},
            include=['metadatas', 'documents']
        )
        
        results = []
        for doc, meta, chunk_id in zip(
            all_chunks['documents'],
            all_chunks['metadatas'],
            all_chunks['ids']
        ):
            section_id = meta.get('section_id')
            if section_id is not None and start_section <= int(section_id) <= end_section:
                results.append(SearchResult(
                    content=doc,
                    metadata=meta,
                    score=1.0,
                    chunk_id=chunk_id
                ))
        
        # Sort by section ID
        results.sort(key=lambda x: int(x.metadata.get('section_id', 0)))
        return results
