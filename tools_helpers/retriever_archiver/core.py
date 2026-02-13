"""
Consolidated Retriever Archiver Module
Optimized for Archiving Conversations and Technical Documentation with Command Syntax.
"""

import os
import re
import json
import uuid
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime

import chromadb
from chromadb.config import Settings
from openai import OpenAI
import PyPDF2
from docx import Document as DocxDocument
from tqdm import tqdm

# --- Core Data Structures ---

class DocumentType(Enum):
    PDF = "pdf"
    DOCX = "docx"
    MARKDOWN = "md"
    TEXT = "txt"
    CODE = "code"
    CONVERSATION = "conversation"

@dataclass
class DocumentChunk:
    content: str
    metadata: Dict[str, Any]
    chunk_id: str
    score: float = 0.0

@dataclass
class ProcessedDocument:
    doc_id: str
    doc_type: DocumentType
    chunks: List[DocumentChunk]
    file_path: Optional[str] = None
    metadata: Dict[str, Any] = None

# --- Helper Components ---

class Embedder:
    """OpenAI Embedding wrapper"""
    def __init__(self, model: str = "text-embedding-3-small", api_key: Optional[str] = None):
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.model = model

    def embed_batch(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = self.client.embeddings.create(input=batch, model=self.model)
            embeddings.extend([e.embedding for e in response.data])
        return embeddings

    def embed_query(self, text: str) -> List[float]:
        response = self.client.embeddings.create(input=[text], model=self.model)
        return response.data[0].embedding

class VectorStore:
    """ChromaDB wrapper optimized for persistence"""
    def __init__(self, persist_directory: str, collection_name: str = "agent_archives"):
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def add_chunks(self, chunks: List[DocumentChunk], embeddings: List[List[float]]):
        ids = [c.chunk_id for c in chunks]
        documents = [c.content for c in chunks]
        metadatas = []
        for c in chunks:
            # Flatten metadata for ChromaDB compatibility
            meta = {}
            for k, v in c.metadata.items():
                if isinstance(v, (str, int, float, bool)):
                    meta[k] = v
                else:
                    meta[k] = str(v)
            metadatas.append(meta)

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )

    def search(self, query_embedding: List[float], top_k: int = 5) -> List[DocumentChunk]:
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )
        
        chunks = []
        if not results['ids'] or not results['ids'][0]:
            return chunks

        ids = results['ids'][0]
        documents = results['documents'][0]
        metadatas = results['metadatas'][0]
        distances = results['distances'][0]

        for i in range(len(ids)):
            chunks.append(DocumentChunk(
                content=documents[i],
                metadata=metadatas[i],
                chunk_id=ids[i],
                score=1.0 - distances[i]
            ))
        return chunks

    def get_context(self, doc_id: str, chunk_index: int, window: int = 1) -> List[DocumentChunk]:
        """Retrieve surrounding chunks for a specific document match"""
        # We use a pattern for chunk IDs: {doc_id}_chunk_{index}
        start = max(0, chunk_index - window)
        end = chunk_index + window
        
        ids = [f"{doc_id}_chunk_{i}" for i in range(start, end + 1)]
        results = self.collection.get(ids=ids, include=['documents', 'metadatas'])
        
        chunks = []
        # Sort results by the inferred index from ID to maintain order
        sorted_indices = sorted(range(len(results['ids'])), 
                               key=lambda i: int(results['ids'][i].split('_chunk_')[-1]))
        
        for i in sorted_indices:
            chunks.append(DocumentChunk(
                content=results['documents'][i],
                metadata=results['metadatas'][i],
                chunk_id=results['ids'][i]
            ))
        return chunks

# --- Main Logic Class ---

class ArchiverRetriever:
    """
    Consolidated class for archiving and retrieving information.
    Optimized for conversations and command-heavy documentation.
    """
    def __init__(self, 
                 storage_path: Optional[str] = None,
                 embedding_model: str = "text-embedding-3-small",
                 llm_model: str = "gpt-4o-mini",
                 api_key: Optional[str] = None):
        
        if not storage_path:
            storage_path = str(Path.home() / ".net-deepagent" / "archives")
        
        os.makedirs(storage_path, exist_ok=True)
        
        self.embedder = Embedder(model=embedding_model, api_key=api_key)
        self.vector_store = VectorStore(persist_directory=storage_path)
        self.llm_client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.llm_model = llm_model

    def archive_conversation(self, messages: List[Dict[str, str]], doc_id: Optional[str] = None, metadata: Optional[Dict] = None) -> str:
        """Process and archive a chat conversation history"""
        if not doc_id:
            doc_id = f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        # Flatten conversation into discrete blocks for embedding
        # We group by exchange (User + Assistant) or similar semantic boundaries
        blocks = []
        current_block = []
        
        for msg in messages:
            role = msg.get('role', 'unknown').upper()
            content = msg.get('content', '')
            if not content: continue
            
            line = f"[{role}]: {content}"
            current_block.append(line)
            
            # Create a chunk after an Assistant response or if the block is getting large
            if role == 'ASSISTANT' or sum(len(l) for l in current_block) > 1000:
                blocks.append("\n".join(current_block))
                current_block = []
        
        if current_block:
            blocks.append("\n".join(current_block))

        base_meta = {
            'doc_id': doc_id,
            'doc_type': DocumentType.CONVERSATION.value,
            'timestamp': datetime.now().isoformat()
        }
        if metadata:
            base_meta.update(metadata)

        chunks = []
        for i, text in enumerate(blocks):
            chunk_meta = base_meta.copy()
            chunk_meta['chunk_index'] = i
            chunks.append(DocumentChunk(
                content=text,
                metadata=chunk_meta,
                chunk_id=f"{doc_id}_chunk_{i}"
            ))

        embeddings = self.embedder.embed_batch([c.content for c in chunks])
        self.vector_store.add_chunks(chunks, embeddings)
        return doc_id

    def archive_documentation(self, file_path: str, metadata: Optional[Dict] = None) -> str:
        """Ingest documentation with special handling for commands"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        doc_id = path.stem
        suffix = path.suffix.lower()
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Custom chunking for Markdown/Text focusing on keeping commands in context
        chunks_text = self._chunk_documentation(content, suffix)
        
        base_meta = {
            'doc_id': doc_id,
            'doc_type': DocumentType.MARKDOWN.value if suffix == '.md' else DocumentType.TEXT.value,
            'file_path': str(path.absolute()),
            'timestamp': datetime.now().isoformat()
        }
        if metadata:
            base_meta.update(metadata)

        chunks = []
        for i, text in enumerate(chunks_text):
            chunk_meta = base_meta.copy()
            chunk_meta['chunk_index'] = i
            # Flag if this chunk contains technical commands or code blocks
            if self._contains_commands(text):
                chunk_meta['contains_commands'] = True
            
            chunks.append(DocumentChunk(
                content=text,
                metadata=chunk_meta,
                chunk_id=f"{doc_id}_chunk_{i}"
            ))

        embeddings = self.embedder.embed_batch([c.content for c in chunks])
        self.vector_store.add_chunks(chunks, embeddings)
        return doc_id

    def _chunk_documentation(self, content: str, suffix: str) -> List[str]:
        """Intelligent chunking that respects code blocks and headers"""
        if suffix == '.md':
            # Split by headers but keep headers in the resulting parts
            # We use a non-empty capture group with re.split to keep the headers
            header_pattern = r'(^#+ .*$)'
            parts = re.split(header_pattern, content, flags=re.MULTILINE)
            
            chunks = []
            current_chunk = ""
            
            for part in parts:
                if not part:
                    continue
                
                # If it's a header, start a new chunk or append if current is empty
                if re.match(r'^#+ ', part):
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = part
                else:
                    current_chunk += part
            
            if current_chunk:
                chunks.append(current_chunk.strip())
            
            return [c for c in chunks if c.strip()]
        else:
            # Fallback to paragraph-based chunking
            paragraphs = re.split(r'\n\s*\n', content)
            chunks = []
            current = []
            for p in paragraphs:
                current.append(p)
                if sum(len(x) for x in current) > 1000:
                    chunks.append("\n\n".join(current))
                    current = []
            if current: chunks.append("\n\n".join(current))
            return chunks

    def _contains_commands(self, text: str) -> bool:
        """Robustly detect terminal commands or shell-like blocks in text"""
        # 1. Check for markdown code blocks with technical languages
        if re.search(r'```(bash|sh|shell|zsh|python|console|powershell|cmd)', text, re.I):
            return True
            
        # 2. Check for shebangs
        if re.search(r'^#!/(bin|usr/bin|usr/local/bin)/[a-z0-9]+', text, re.M):
            return True
            
        # 3. Check for shell prompts and common command patterns
        patterns = [
            r'^[a-z0-9._-]+@[a-z0-9._-]+:?.*[#\$] ',  # user@host prompt
            r'^[\/~][A-Za-z0-9._\-/]*[#\$] ',          # /path$ or ~$ prompt
            r'^[#\$] ',                                # simple # or $ prompt
            r'^>>> ',                                  # Python REPL
            r'^[A-Za-z0-9\._-]+\(config\)#',           # Cisco config prompt
            r'^[A-Za-z0-9\._-]+[>#]',                  # Cisco user/exec prompt
            r'^\.?/[a-z0-9._-]+ ',                     # ./command or /path/to/cmd
            r'^(sudo|apt-get|yum|dnf|git|docker|ping|traceroute|ssh|curl|wget|ip|ifconfig|nmcli|systemctl) ' # Common CLI
        ]
        
        for pattern in patterns:
            if re.search(pattern, text, re.M):
                return True
                
        return False

    def retrieve(self, query: str, top_k: int = 3, expand_window: int = 1) -> List[DocumentChunk]:
        """Retrieve relevant information with context expansion"""
        query_emb = self.embedder.embed_query(query)
        initial_matches = self.vector_store.search(query_emb, top_k=top_k)
        
        # Deduplication and expansion
        expanded_chunks = {}
        for match in initial_matches:
            doc_id = match.metadata.get('doc_id')
            idx = int(match.metadata.get('chunk_index', 0))
            
            # Fetch surrounding context
            context = self.vector_store.get_context(doc_id, idx, window=expand_window)
            for ctx in context:
                expanded_chunks[ctx.chunk_id] = ctx
        
        # Sort by doc_id and then chunk_index to maintain reading flow
        final_list = list(expanded_chunks.values())
        final_list.sort(key=lambda x: (x.metadata.get('doc_id'), int(x.metadata.get('chunk_index', 0))))
        
        return final_list

    def rag_query(self, query: str) -> Dict[str, Any]:
        """End-to-end RAG workflow"""
        contexts = self.retrieve(query)
        if not contexts:
            return {"answer": "I couldn't find any relevant archived information to answer that question.", "sources": []}
        
        # Prepare context for LLM with timestamps
        context_str = ""
        sources = set()
        for i, chunk in enumerate(contexts):
            doc_id = chunk.metadata.get('doc_id')
            timestamp = chunk.metadata.get('timestamp', 'Unknown')
            sources.add(doc_id)
            context_str += f"\n--- [Source: {doc_id} | Time: {timestamp}] ---\n{chunk.content}\n"

        system_prompt = (
            "You are an AI assistant with access to archived conversations and technical documentation. "
            "Use the provided context to answer the user's question accurately. "
            "Timestamps are provided for each source; if information is contradictory, prioritize the more recent entries. "
            "If the information is from a past conversation, refer to it as 'our previous discussion' or 'our discussion on [date]'. "
            "If it contains commands, prioritize showing them correctly. "
            "If you cannot find the answer in the context, be honest about it."
        )
        
        user_prompt = f"Context:\n{context_str}\n\nQuestion: {query}"
        
        response = self.llm_client.chat.completions.create(
            model=self.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2
        )
        
        return {
            "answer": response.choices[0].message.content,
            "sources": list(sources)
        }
