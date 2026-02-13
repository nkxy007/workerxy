# Quick Start Guide - Context-Aware RAG System

## 🎯 What You Have

A complete, production-ready RAG system with intelligent context expansion. Unlike standard RAG that retrieves isolated chunks, this system retrieves **matched content + surrounding context** for better answers.

## 📦 What's Included

```
context_rag_tool/
├── Core System Files
│   ├── config.py              - Configuration management
│   ├── document_processor.py  - Processes PDF, DOCX, Markdown, Text
│   ├── embedder.py           - OpenAI & local embeddings
│   ├── vector_store.py       - ChromaDB integration
│   ├── retriever.py          - Smart context expansion
│   ├── llm_interface.py      - LLM augmentation
│   └── rag_system.py         - Main system orchestrator
│
├── Interfaces
│   ├── cli.py                - Command-line interface
│   ├── demo.py               - Interactive demo
│   └── test_rag.py           - Complete test suite
│
├── Documentation
│   ├── README.md             - Comprehensive guide
│   ├── requirements.txt      - Dependencies
│   └── .env.example          - Environment template
│
└── Sample Data
    └── sample_docs/
        ├── docker_networking.md
        └── python_guide.txt
```

## 🚀 Installation (3 Steps)

### Step 1: Install Dependencies

```bash
cd context_rag_tool
pip install -r requirements.txt
```

**Required packages:**
- chromadb - Vector database
- openai - Embeddings & LLM
- pypdf2 - PDF processing
- python-docx - Word processing
- sentence-transformers - Local embeddings (optional)
- rich - Beautiful CLI output
- pytest - Testing framework

### Step 2: Set Up API Key

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and add your OpenAI API key
# OPENAI_API_KEY=sk-...
```

### Step 3: Verify Installation

```bash
python verify_structure.py
```

## 💡 Usage Examples

### Command Line Interface

**1. Ingest Documents**
```bash
# Single file
python cli.py ingest -f sample_docs/docker_networking.md -v

# Entire directory
python cli.py ingest -d sample_docs/ -v
```

**2. Query the System**
```bash
# Ask a question
python cli.py query "How do I create a Docker network?" -v

# Retrieve only (no LLM)
python cli.py query "What are network drivers?" -r -v

# Custom parameters
python cli.py query "Explain Docker networking" \
    --top-k 5 \
    --context-window 3 \
    --model gpt-4 \
    -v
```

**3. Interactive Mode**
```bash
python cli.py interactive -v
```

**4. Check Statistics**
```bash
python cli.py stats
```

**5. Clear Database**
```bash
python cli.py clear
```

### Python API

```python
from rag_system import ContextRAG
from config import get_config

# Initialize
config = get_config(
    retrieval={'top_k': 3, 'context_window': 2},
    llm={'model': 'gpt-4o-mini'},
    verbose=True
)

rag = ContextRAG(config)

# Ingest
rag.ingest_document('docs/manual.pdf')

# Query
result = rag.query("How do I configure logging?")
print(result['answer'])

# Access sources
for source in result['sources']:
    print(f"  - {source['doc_id']} (pages {source['page_range']})")
```

## 🎨 Key Features Explained

### 1. Context Expansion

**Traditional RAG:**
```
Query: "What is docker network inspect?"
→ Retrieved: "Use docker network inspect to view network details."
→ Problem: Missing syntax, examples, options
```

**Context-Aware RAG:**
```
Query: "What is docker network inspect?"
→ Retrieved: Matched section + 2 sections before + 2 sections after
→ Result: Full command reference, syntax, examples, related commands
```

### 2. Adaptive Context Windows

The system automatically adjusts context based on chunk size:

- **Small chunks** (<200 tokens) → Expand more (±3 sections)
- **Medium chunks** (200-800 tokens) → Default (±2 sections)
- **Large chunks** (>800 tokens) → Expand less (±1 section)

### 3. Intelligent Deduplication

When multiple matches have overlapping contexts:

```
Match 1: Pages 3-5
Match 2: Pages 4-6
→ Merged: Pages 3-6 (no duplication)
```

### 4. Re-ranking

After expansion, contexts are re-scored by relevance:

```python
# Not just initial similarity, but relevance of entire expanded context
contexts = sorted(contexts, key=lambda x: relevance_score(query, x.full_context))
```

## 🔧 Configuration Options

### Embedding Settings
```python
embedding={
    'provider': 'openai',  # or 'local' for sentence-transformers
    'model': 'text-embedding-3-small',
    'batch_size': 100
}
```

### Retrieval Settings
```python
retrieval={
    'top_k': 3,                     # Initial matches
    'context_window': 2,            # ±N pages/sections
    'adaptive_context': True,       # Adjust based on chunk size
    'max_context_tokens': 32000,    # Token limit
    'deduplicate_overlaps': True,   # Merge overlapping contexts
    're_rank_context': True,        # Re-score by relevance
    'similarity_threshold': 0.7     # Minimum match score
}
```

### LLM Settings
```python
llm={
    'provider': 'openai',
    'model': 'gpt-4o-mini',
    'temperature': 0.1,
    'max_tokens': 4000,
    'include_citations': True
}
```

## 🧪 Testing

```bash
# Run all tests
pytest test_rag.py -v

# Run specific test
pytest test_rag.py::TestDocumentProcessor -v

# With coverage
pytest test_rag.py --cov=. --cov-report=html
```

## 📊 Supported Document Types

| Format | Extension | Chunking Strategy |
|--------|-----------|-------------------|
| PDF | .pdf | Page-based |
| Word | .docx | Paragraph-based (simulated pages) |
| Markdown | .md | Hierarchical by headers (H1, H2, H3) |
| Text | .txt | Paragraph-based with semantic boundaries |
| Code | .py, .js, .java, .cpp | Text-based (can be enhanced) |

## 💭 Common Use Cases

### Technical Documentation
```bash
# Ingest API docs
python cli.py ingest -f api_reference.md

# Ask about specific commands
python cli.py query "What parameters does the create_user endpoint accept?"
```

### Code Documentation
```bash
# Ingest codebase docs
python cli.py ingest -d docs/

# Get implementation details
python cli.py query "How do I implement authentication?"
```

### Knowledge Base
```bash
# Ingest policy documents
python cli.py ingest -d policies/

# Query for specific policies
python cli.py query "What is the remote work policy?"
```

## 🎯 Best Practices

1. **Document Organization**: Organize docs with clear headers/sections for better chunking

2. **Context Window**: Start with ±2, increase for very fragmented content

3. **Top K**: Use 3-5 for balanced coverage vs. noise

4. **Similarity Threshold**: Adjust if getting too many/few results (default 0.7)

5. **Token Budget**: Monitor context tokens, adjust max_context_tokens if hitting limits

## 🐛 Troubleshooting

**No results found:**
- Lower similarity_threshold
- Increase top_k
- Check if documents are ingested (`python cli.py stats`)

**Too many irrelevant results:**
- Increase similarity_threshold
- Decrease top_k
- Use more specific queries

**Context too large:**
- Reduce context_window
- Decrease max_context_tokens
- Disable adaptive_context

**Out of memory:**
- Process documents in smaller batches
- Reduce embedding batch_size
- Clear database between large ingestions

## 📚 Next Steps

1. **Customize chunking**: Modify `document_processor.py` for your document types

2. **Add filters**: Extend metadata filtering in queries

3. **Enhance re-ranking**: Implement custom scoring logic

4. **Build UI**: Create web interface using the Python API

5. **Production deployment**: Add caching, monitoring, error handling

## 🤝 Support

For issues:
1. Check `README.md` for detailed documentation
2. Run `verify_structure.py` to validate setup
3. Review sample documents in `sample_docs/`
4. Run tests to ensure system works: `pytest test_rag.py -v`

---

**Happy RAG-ing!** 🚀

For advanced features and API reference, see README.md
