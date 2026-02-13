"""
Test suite for Context-Aware RAG system
"""
import pytest
import tempfile
import shutil
from pathlib import Path

from document_processor import DocumentProcessor, DocumentType
from embedder import get_embedder
from vector_store import VectorStore
from rag_system import ContextRAG
from config import get_config


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests"""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def sample_markdown(temp_dir):
    """Create sample markdown file"""
    content = """# Docker Networking Guide

## Introduction
Docker networking allows containers to communicate with each other and external services.

## Basic Commands

### List Networks
Use the following command to list all networks:
```bash
docker network ls
```

### Create Network
Create a new network with:
```bash
docker network create my-network
```

### Inspect Network
Get detailed information about a network:
```bash
docker network inspect my-network
```

## Advanced Topics

### Network Drivers
Docker supports multiple network drivers:
- bridge: Default driver
- host: Remove network isolation
- overlay: Multi-host networking
- macvlan: Assign MAC address to container

### Custom Networks
You can create custom networks with specific configurations for better isolation and control.

## Troubleshooting

### Common Issues
If containers can't communicate, check:
1. Network configuration
2. Firewall rules
3. Container network settings

### Debug Commands
Use these commands to debug network issues:
```bash
docker network inspect <network-name>
docker logs <container-name>
```
"""
    
    file_path = Path(temp_dir) / "docker_networking.md"
    file_path.write_text(content)
    return str(file_path)


@pytest.fixture
def sample_text(temp_dir):
    """Create sample text file"""
    content = """Python Programming Best Practices

Code Organization
Always organize your code into logical modules and packages. Use meaningful names for files and directories.

Documentation
Write docstrings for all functions, classes, and modules. Use clear and concise language.

Testing
Write unit tests for all functions. Use pytest or unittest framework. Aim for high code coverage.

Error Handling
Use try-except blocks appropriately. Don't catch all exceptions blindly. Log errors for debugging.

Code Style
Follow PEP 8 guidelines. Use consistent indentation. Keep lines under 79 characters when possible.

Version Control
Commit frequently with meaningful messages. Use branches for new features. Review code before merging.
"""
    
    file_path = Path(temp_dir) / "python_guide.txt"
    file_path.write_text(content)
    return str(file_path)


class TestDocumentProcessor:
    """Test document processing"""
    
    def test_markdown_processing(self, sample_markdown):
        """Test markdown file processing"""
        doc = DocumentProcessor.process_document(sample_markdown)
        
        assert doc.doc_type == DocumentType.MARKDOWN
        assert doc.total_pages > 0
        assert len(doc.pages) > 0
        assert not doc.metadata['is_paginated']
        
        # Check hierarchical structure
        for page in doc.pages:
            assert 'section_id' in page.metadata
            assert page.content
    
    def test_text_processing(self, sample_text):
        """Test text file processing"""
        doc = DocumentProcessor.process_document(sample_text)
        
        assert doc.doc_type == DocumentType.TEXT
        assert doc.total_pages > 0
        assert len(doc.pages) > 0
    
    def test_type_detection(self, sample_markdown, sample_text):
        """Test document type detection"""
        assert DocumentProcessor.detect_type(sample_markdown) == DocumentType.MARKDOWN
        assert DocumentProcessor.detect_type(sample_text) == DocumentType.TEXT
        assert DocumentProcessor.detect_type("test.pdf") == DocumentType.PDF


class TestEmbedder:
    """Test embedding functionality"""
    
    def test_local_embedder(self):
        """Test local embedder"""
        embedder = get_embedder(provider='local')
        
        # Test single text
        text = "This is a test sentence."
        embedding = embedder.embed(text)
        
        assert isinstance(embedding, list)
        assert len(embedding) > 0
        assert all(isinstance(x, float) for x in embedding)
        
        # Test batch
        texts = ["First sentence.", "Second sentence.", "Third sentence."]
        embeddings = embedder.embed(texts)
        
        assert len(embeddings) == 3
        assert all(len(emb) == len(embedding) for emb in embeddings)
    
    def test_token_counting(self):
        """Test token counting"""
        embedder = get_embedder(provider='local')
        
        text = "This is a test."
        count = embedder.count_tokens(text)
        
        assert count > 0
        assert isinstance(count, int)


class TestVectorStore:
    """Test vector store operations"""
    
    def test_add_and_search(self, temp_dir):
        """Test adding documents and searching"""
        # Create vector store
        store = VectorStore(
            collection_name="test_collection",
            persist_directory=str(Path(temp_dir) / "chroma_test")
        )
        
        # Create test data
        embedder = get_embedder(provider='local')
        
        docs = [
            "Docker networks allow container communication.",
            "Python is a programming language.",
            "Testing is important for code quality."
        ]
        
        embeddings = embedder.embed(docs)
        metadatas = [
            {'doc_id': 'doc1', 'page_num': 1},
            {'doc_id': 'doc2', 'page_num': 1},
            {'doc_id': 'doc3', 'page_num': 1}
        ]
        
        # Add documents
        store.add_documents(docs, embeddings, metadatas)
        
        assert store.count() == 3
        
        # Search
        query = "How do containers communicate?"
        query_emb = embedder.embed(query)
        results = store.search(query_emb, top_k=2)
        
        assert len(results) == 2
        assert all(hasattr(r, 'content') for r in results)
        assert all(hasattr(r, 'score') for r in results)
        
        # First result should be about Docker networks
        assert 'docker' in results[0].content.lower() or 'container' in results[0].content.lower()
        
        # Clean up
        store.delete_collection()


class TestRAGSystem:
    """Test end-to-end RAG system"""
    
    def test_ingestion(self, temp_dir, sample_markdown):
        """Test document ingestion"""
        config = get_config(
            vector_db={'persist_directory': str(Path(temp_dir) / "chroma_rag")},
            verbose=False
        )
        
        rag = ContextRAG(config)
        
        # Ingest document
        result = rag.ingest_document(sample_markdown)
        
        assert 'doc_id' in result
        assert result['num_chunks'] > 0
        assert result['doc_type'] == 'md'
        
        # Check stats
        stats = rag.get_stats()
        assert stats['total_chunks'] > 0
        
        # Clean up
        rag.clear_database()
    
    def test_retrieval_only(self, temp_dir, sample_markdown):
        """Test retrieval without LLM augmentation"""
        config = get_config(
            vector_db={'persist_directory': str(Path(temp_dir) / "chroma_rag2")},
            verbose=False
        )
        
        rag = ContextRAG(config)
        
        # Ingest document
        rag.ingest_document(sample_markdown)
        
        # Query with retrieval only
        result = rag.query(
            "How do I list Docker networks?",
            retrieve_only=True
        )
        
        assert 'contexts' in result
        assert len(result['contexts']) > 0
        assert 'citations' in result
        
        # Check that context mentions docker network commands
        context_text = result['contexts'][0]['text'].lower()
        assert 'docker' in context_text or 'network' in context_text
        
        # Clean up
        rag.clear_database()
    
    def test_context_expansion(self, temp_dir, sample_markdown):
        """Test that context expansion works"""
        config = get_config(
            vector_db={'persist_directory': str(Path(temp_dir) / "chroma_rag3")},
            retrieval={'context_window': 2},
            verbose=False
        )
        
        rag = ContextRAG(config)
        
        # Ingest document
        rag.ingest_document(sample_markdown)
        
        # Query
        result = rag.query(
            "What is docker network inspect command?",
            retrieve_only=True
        )
        
        # Should retrieve multiple sections due to context expansion
        assert len(result['contexts']) > 0
        
        # Check that sections were expanded
        first_context = result['contexts'][0]
        assert 'sections' in first_context
        assert len(first_context['sections']) > 1  # Should have expanded context
        
        # Clean up
        rag.clear_database()


def test_integration_workflow(temp_dir, sample_markdown, sample_text):
    """Test complete workflow: ingest multiple docs and query"""
    config = get_config(
        vector_db={'persist_directory': str(Path(temp_dir) / "chroma_integration")},
        retrieval={'context_window': 1},
        verbose=False
    )
    
    rag = ContextRAG(config)
    
    # Ingest multiple documents
    results = rag.ingest_documents([sample_markdown, sample_text])
    
    assert len(results) == 2
    assert all('doc_id' in r for r in results)
    
    # Query about Docker
    result1 = rag.query("How to create a Docker network?", retrieve_only=True)
    assert len(result1['contexts']) > 0
    
    # Query about Python
    result2 = rag.query("What are Python best practices?", retrieve_only=True)
    assert len(result2['contexts']) > 0
    
    # Verify correct documents were retrieved
    context1_text = result1['contexts'][0]['text'].lower()
    assert 'docker' in context1_text
    
    context2_text = result2['contexts'][0]['text'].lower()
    assert 'python' in context2_text or 'pep' in context2_text
    
    # Check stats
    stats = rag.get_stats()
    assert stats['total_chunks'] >= len(results)
    
    # Clean up
    rag.clear_database()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
