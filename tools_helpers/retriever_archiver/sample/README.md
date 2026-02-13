# Context-Aware RAG System 🚀

A production-ready Retrieval-Augmented Generation (RAG) system with intelligent context expansion. Unlike traditional RAG systems that retrieve isolated chunks, this tool retrieves matched content **plus surrounding context** for better answers.

## 🌟 Key Features

### Smart Context Expansion
- **Paginated Documents** (PDF, DOCX): Retrieves ±N pages around matched content
- **Pageless Documents** (Markdown, Text): Retrieves ±N sections using hierarchical structure
- **Adaptive Windows**: Automatically adjusts context size based on chunk size

### Advanced Retrieval
- ✅ **Overlap Deduplication**: Merges overlapping contexts intelligently
- ✅ **Re-ranking**: Re-scores expanded contexts by relevance to query
- ✅ **Token Management**: Respects LLM context limits (default 32k)
- ✅ **Citation Tracking**: Returns precise source locations (pages/sections)

### Production-Ready
- 📚 Multiple embedding providers (OpenAI, local)
- 🤖 Configurable LLM models (GPT-4o-mini, GPT-4, etc.)
- 💾 Persistent vector storage (ChromaDB)
- 🎯 Hierarchical semantic chunking for better structure
- 🔧 Fully configurable via Python API or CLI

## 📖 Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [How It Works](#how-it-works)
- [Usage Examples](#usage-examples)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Testing](#testing)
- [Architecture](#architecture)

## 🚀 Installation

### Prerequisites
- Python 3.8+
- OpenAI API key (for embeddings and LLM)

### Setup

```bash
# Clone or download the repository
cd context_rag_tool

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env and add your OpenAI API key
```

## ⚡ Quick Start

### 1. Ingest Documents

```bash
# Ingest a single file
python cli.py ingest -f sample_docs/docker_networking.md -v

# Ingest entire directory
python cli.py ingest -d sample_docs/ -v
```

### 2. Query the System

```bash
# Ask a question
python cli.py query "How do I create a Docker network?" -v

# Retrieve context only (no LLM)
python cli.py query "What are Docker network drivers?" -r -v
```

### 3. Interactive Mode

```bash
python cli.py interactive -v
```

### 4. Check Statistics

```bash
python cli.py stats
```

## 🧠 How It Works

Traditional RAG systems retrieve isolated chunks, which often lack context. Our system solves this by:

### Standard RAG
```
Query: "What is docker network inspect?"
→ Retrieves: Single chunk about inspect command
→ Missing: Command syntax, usage examples, related commands
```

### Context-Aware RAG
```
Query: "What is docker network inspect?"
→ Retrieves: Matched chunk + 2 sections before + 2 sections after
→ Includes: Full command reference, examples, troubleshooting context
→ Result: Complete, actionable answer
```

### Architecture Flow

```
┌─────────────┐
│  Document   │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────┐
│  Hierarchical Chunking      │
│  • Pages (PDF/DOCX)        │
│  • Sections (MD/TXT/Code)  │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│  Embedding + Vector Store   │
│  (ChromaDB)                │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│  Query                      │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│  Semantic Search (Top K)    │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│  Context Expansion          │
│  • Adaptive window         │
│  • Deduplication          │
│  • Re-ranking             │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│  LLM Augmentation          │
│  (with citations)          │
└─────────────────────────────┘
```

## 📚 Usage Examples

### Python API

```python
from rag_system import ContextRAG
from config import get_config

# Initialize with custom config
config = get_config(
    embedding={'provider': 'openai', 'model': 'text-embedding-3-small'},
    llm={'model': 'gpt-4o-mini'},
    retrieval={'top_k': 5, 'context_window': 2},
    verbose=True
)

rag = ContextRAG(config)

# Ingest documents
rag.ingest_document('docs/manual.pdf')
rag.ingest_documents(['docs/guide1.md', 'docs/guide2.txt'])

# Query
result = rag.query("How do I configure logging?")

print(result['answer'])
print(f"Sources: {result['num_sources']}")
for citation in result['sources']:
    print(f"  - {citation['doc_id']} (pages {citation.get('page_range', 'N/A')})")

# Retrieval only (no LLM)
retrieval_result = rag.query("Show me examples", retrieve_only=True)
for ctx in retrieval_result['contexts']:
    print(ctx['text'])
```

### CLI Examples

```bash
# Ingest with verbose output
python cli.py ingest -d documentation/ -v

# Query with custom parameters
python cli.py query "What are best practices?" \
  --top-k 5 \
  --context-window 3 \
  --model gpt-4 \
  -v

# Save results to file
python cli.py query "Explain the process" -o results.json

# Interactive session
python cli.py interactive -v

# Clear database
python cli.py clear --force
```

## ⚙️ Configuration

### Environment Variables (.env)

```bash
OPENAI_API_KEY=your_api_key_here
```

### Python Configuration

```python
from config import get_config

config = get_config(
    # Embedding settings
    embedding={
        'provider': 'openai',  # or 'local'
        'model': 'text-embedding-3-small',
        'batch_size': 100
    },
    
    # Chunking strategy
    chunking={
        'pageless_strategy': 'hierarchical_semantic',  # or 'fixed', 'sliding'
        'chunk_size': 512,
        'chunk_overlap': 50
    },
    
    # Retrieval settings
    retrieval={
        'top_k': 3,
        'context_window': 2,  # ±2 pages/sections
        'adaptive_context': True,
        'max_context_tokens': 32000,
        'deduplicate_overlaps': True,
        're_rank_context': True,
        'similarity_threshold': 0.7
    },
    
    # LLM settings
    llm={
        'provider': 'openai',
        'model': 'gpt-4o-mini',
        'temperature': 0.1,
        'max_tokens': 4000,
        'include_citations': True
    },
    
    # Vector DB
    vector_db={
        'provider': 'chromadb',
        'collection_name': 'documents',
        'persist_directory': './chroma_db'
    },
    
    verbose=True
)
```

### Supported Models

**Embeddings:**
- OpenAI: `text-embedding-3-small`, `text-embedding-3-large`, `text-embedding-ada-002`
- Local: `all-MiniLM-L6-v2`, `all-mpnet-base-v2` (via sentence-transformers)

**LLMs:**
- OpenAI: `gpt-4o-mini`, `gpt-4o`, `gpt-4-turbo`, `gpt-3.5-turbo`

## 🧪 Testing

```bash
# Run all tests
pytest test_rag.py -v

# Run specific test
pytest test_rag.py::TestDocumentProcessor::test_markdown_processing -v

# Run with coverage
pytest test_rag.py --cov=. --cov-report=html
```

### Test Coverage

The test suite covers:
- ✅ Document processing (PDF, DOCX, Markdown, Text)
- ✅ Embedding generation (OpenAI, local)
- ✅ Vector storage and retrieval
- ✅ Context expansion logic
- ✅ Deduplication algorithms
- ✅ End-to-end workflows

## 📊 API Reference

### ContextRAG Class

```python
class ContextRAG:
    def __init__(self, config: RAGConfig = None)
    
    def ingest_document(self, file_path: str) -> Dict[str, Any]
    """Ingest a single document"""
    
    def ingest_documents(self, file_paths: List[str]) -> List[Dict[str, Any]]
    """Ingest multiple documents"""
    
    def query(self, question: str, retrieve_only: bool = False) -> Dict[str, Any]
    """Query the RAG system"""
    
    def get_stats(self) -> Dict[str, Any]
    """Get system statistics"""
    
    def clear_database(self)
    """Clear the vector database"""
```

### Query Response Format

```python
{
    'query': 'User question',
    'answer': 'Generated answer with citations',
    'sources': [
        {
            'source_id': 1,
            'doc_id': 'docker_networking',
            'match_score': 0.89,
            'page_range': '3-5',  # or 'section_range' for pageless
            'type': 'paginated'
        }
    ],
    'num_sources': 3,
    'usage': {
        'prompt_tokens': 1500,
        'completion_tokens': 300,
        'total_tokens': 1800
    }
}
```

## 🏗️ Architecture

### Project Structure

```
context_rag_tool/
├── config.py                  # Configuration management
├── document_processor.py      # Document parsing (PDF, MD, TXT)
├── embedder.py               # Embedding generation
├── vector_store.py           # ChromaDB wrapper
├── retriever.py              # Context expansion logic
├── llm_interface.py          # LLM augmentation
├── rag_system.py             # Main RAG system
├── cli.py                    # Command-line interface
├── test_rag.py               # Test suite
├── requirements.txt          # Dependencies
├── sample_docs/              # Sample documents
│   ├── docker_networking.md
│   └── python_guide.txt
└── README.md                 # This file
```

### Key Components

1. **Document Processor**: Handles multiple file formats and extracts structured content
2. **Embedder**: Generates embeddings using OpenAI or local models
3. **Vector Store**: Manages ChromaDB for efficient similarity search
4. **Context Retriever**: Expands matched chunks with surrounding context
5. **LLM Interface**: Augments retrieval with LLM-generated answers

## 🎯 Use Cases

### Technical Documentation
- API references with command syntax
- Installation guides with step-by-step instructions
- Troubleshooting manuals with related diagnostics

### Code Documentation
- Function definitions with usage examples
- Class hierarchies with inheritance context
- Configuration files with dependent settings

### Knowledge Base
- Policy documents with related clauses
- Training materials with prerequisite information
- Research papers with supporting evidence

## 🔧 Advanced Features

### Adaptive Context Windows

The system automatically adjusts context window based on chunk size:

```python
# Small chunks (< 200 tokens) → expand more
context_window = 3

# Large chunks (> 800 tokens) → expand less  
context_window = 1

# Medium chunks → default
context_window = 2
```

### Overlap Deduplication

When multiple matches have overlapping contexts, the system merges them:

```
Match 1: Pages 3-5
Match 2: Pages 4-6
→ Merged: Pages 3-6 (no duplication)
```

### Re-ranking

After expansion, contexts are re-ranked by relevance to the original query:

```python
# Each expanded context is re-scored
relevance_score = cosine_similarity(query_embedding, context_embedding)
# Sorted by relevance, not just initial match score
```

## 🤝 Contributing

Contributions are welcome! Areas for improvement:

- Additional document format support (HTML, LaTeX)
- More embedding providers (Cohere, HuggingFace)
- Advanced chunking strategies
- Batch processing optimizations
- Web UI interface

## 📝 License

MIT License - feel free to use in your projects!

## 🙏 Acknowledgments

Built with:
- ChromaDB for vector storage
- OpenAI for embeddings and LLM
- Sentence Transformers for local embeddings
- Rich for beautiful CLI output

## 📧 Support

For issues or questions:
1. Check the test suite for examples
2. Review the sample documents in `sample_docs/`
3. Open an issue with detailed reproduction steps

---

**Happy RAG-ing!** 🚀
