#!/usr/bin/env python3
"""
Demo script for Context-Aware RAG System
Demonstrates key features without requiring OpenAI API
"""
import os
import sys
from pathlib import Path

# Ensure we can import the modules
sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table

from document_processor import DocumentProcessor
from embedder import get_embedder
from vector_store import VectorStore
from retriever import ContextRetriever
from config import get_config

console = Console()


def demo_document_processing():
    """Demonstrate document processing capabilities"""
    console.print("\n[bold cyan]═══ Demo 1: Document Processing ═══[/bold cyan]\n")
    
    sample_file = "sample_docs/docker_networking.md"
    
    if not os.path.exists(sample_file):
        console.print(f"[red]Sample file not found: {sample_file}[/red]")
        return
    
    console.print(f"[yellow]Processing: {sample_file}[/yellow]")
    
    # Process document
    doc = DocumentProcessor.process_document(sample_file)
    
    # Display results
    table = Table(title="Document Processing Results")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="yellow")
    
    table.add_row("Document ID", doc.doc_id)
    table.add_row("Document Type", doc.doc_type.value)
    table.add_row("Total Sections", str(doc.total_pages))
    table.add_row("Is Paginated", str(doc.metadata.get('is_paginated', False)))
    
    console.print(table)
    
    # Show first few sections
    console.print("\n[bold green]First 3 Sections:[/bold green]\n")
    
    for i, page in enumerate(doc.pages[:3], 1):
        title = page.metadata.get('section_title', 'Untitled')
        level = page.metadata.get('section_level', 0)
        preview = page.content[:150] + "..." if len(page.content) > 150 else page.content
        
        console.print(Panel(
            preview,
            title=f"Section {i}: {title} (Level {level})",
            border_style="green"
        ))


def demo_embedding():
    """Demonstrate embedding generation"""
    console.print("\n[bold cyan]═══ Demo 2: Embedding Generation ═══[/bold cyan]\n")
    
    console.print("[yellow]Using local embedding model (no API key needed)[/yellow]\n")
    
    # Initialize local embedder
    embedder = get_embedder(provider='local', model='all-MiniLM-L6-v2')
    
    # Sample texts
    texts = [
        "Docker networking enables container communication.",
        "Python is a high-level programming language.",
        "Machine learning models require training data."
    ]
    
    console.print("[green]Generating embeddings for sample texts...[/green]\n")
    
    # Generate embeddings
    embeddings = embedder.embed(texts)
    
    # Display results
    table = Table(title="Embedding Results")
    table.add_column("Text", style="cyan", width=50)
    table.add_column("Embedding Dimension", style="yellow")
    table.add_column("First 5 Values", style="magenta")
    
    for text, emb in zip(texts, embeddings):
        preview = text[:47] + "..." if len(text) > 50 else text
        first_values = ", ".join([f"{x:.3f}" for x in emb[:5]])
        table.add_row(preview, str(len(emb)), first_values)
    
    console.print(table)
    
    # Calculate similarity
    import numpy as np
    
    console.print("\n[bold green]Similarity Scores:[/bold green]\n")
    
    sim_table = Table()
    sim_table.add_column("Text Pair", style="cyan")
    sim_table.add_column("Cosine Similarity", style="yellow")
    
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            similarity = np.dot(embeddings[i], embeddings[j]) / (
                np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[j])
            )
            text_pair = f"{i+1} ↔ {j+1}"
            sim_table.add_row(text_pair, f"{similarity:.4f}")
    
    console.print(sim_table)


def demo_vector_store():
    """Demonstrate vector store operations"""
    console.print("\n[bold cyan]═══ Demo 3: Vector Store & Retrieval ═══[/bold cyan]\n")
    
    import tempfile
    import shutil
    
    # Create temporary directory
    temp_dir = tempfile.mkdtemp()
    
    try:
        console.print("[yellow]Creating vector store with sample data...[/yellow]\n")
        
        # Initialize components
        embedder = get_embedder(provider='local')
        vector_store = VectorStore(
            collection_name="demo_collection",
            persist_directory=temp_dir
        )
        
        # Sample documents
        docs = [
            "Docker network create command creates a new network for containers to communicate.",
            "The docker network ls command lists all networks available on the system.",
            "Use docker network inspect to view detailed information about a specific network.",
            "Python's list comprehensions provide a concise way to create lists.",
            "Error handling in Python uses try-except blocks to catch exceptions.",
            "The pytest framework is commonly used for testing Python applications."
        ]
        
        # Generate embeddings
        embeddings = embedder.embed(docs)
        
        # Create metadata
        metadatas = [
            {'doc_id': 'docker_guide', 'section_id': 0, 'topic': 'networking'},
            {'doc_id': 'docker_guide', 'section_id': 1, 'topic': 'networking'},
            {'doc_id': 'docker_guide', 'section_id': 2, 'topic': 'networking'},
            {'doc_id': 'python_guide', 'section_id': 0, 'topic': 'syntax'},
            {'doc_id': 'python_guide', 'section_id': 1, 'topic': 'error_handling'},
            {'doc_id': 'python_guide', 'section_id': 2, 'topic': 'testing'},
        ]
        
        # Add to vector store
        vector_store.add_documents(docs, embeddings, metadatas)
        
        console.print(f"[green]✓ Added {vector_store.count()} documents to vector store[/green]\n")
        
        # Perform searches
        queries = [
            "How do I list Docker networks?",
            "What is the best way to test Python code?"
        ]
        
        for query in queries:
            console.print(f"[bold cyan]Query:[/bold cyan] {query}\n")
            
            # Search
            query_emb = embedder.embed(query)
            results = vector_store.search(query_emb, top_k=2)
            
            # Display results
            for i, result in enumerate(results, 1):
                console.print(Panel(
                    f"[yellow]Score: {result.score:.4f}[/yellow]\n\n{result.content}",
                    title=f"Result {i}: {result.metadata['doc_id']} (Topic: {result.metadata['topic']})",
                    border_style="green"
                ))
            
            console.print()
    
    finally:
        # Cleanup
        shutil.rmtree(temp_dir)


def demo_context_expansion():
    """Demonstrate context expansion logic"""
    console.print("\n[bold cyan]═══ Demo 4: Context Expansion ═══[/bold cyan]\n")
    
    import tempfile
    import shutil
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        console.print("[yellow]Simulating context expansion with hierarchical sections...[/yellow]\n")
        
        # Process sample document
        sample_file = "sample_docs/docker_networking.md"
        
        if not os.path.exists(sample_file):
            console.print(f"[red]Sample file not found: {sample_file}[/red]")
            return
        
        doc = DocumentProcessor.process_document(sample_file)
        
        # Initialize components
        embedder = get_embedder(provider='local')
        vector_store = VectorStore(
            collection_name="demo_expansion",
            persist_directory=temp_dir
        )
        
        # Prepare documents for storage
        texts = [page.content for page in doc.pages]
        embeddings = embedder.embed_batch(texts, batch_size=10)
        
        metadatas = []
        ids = []
        for i, page in enumerate(doc.pages):
            metadata = {
                'doc_id': doc.doc_id,
                'section_id': page.metadata.get('section_id', i),
                'section_title': page.metadata.get('section_title', 'Untitled'),
                'is_paginated': False
            }
            metadatas.append(metadata)
            ids.append(f"{doc.doc_id}_section_{i}")
        
        # Add to vector store
        vector_store.add_documents(texts, embeddings, metadatas, ids)
        
        console.print(f"[green]✓ Indexed {len(texts)} sections[/green]\n")
        
        # Create retriever with context expansion
        retriever = ContextRetriever(
            vector_store=vector_store,
            embedder=embedder,
            top_k=1,
            context_window=2,  # ±2 sections
            adaptive_context=True,
            deduplicate_overlaps=True,
            re_rank_context=False
        )
        
        # Query
        query = "What are the Docker network drivers?"
        console.print(f"[bold cyan]Query:[/bold cyan] {query}\n")
        
        result = retriever.retrieve(query, verbose=True)
        
        # Display expanded context
        console.print("\n[bold green]Expanded Context:[/bold green]\n")
        
        for i, ctx in enumerate(result.contexts, 1):
            sections = ctx.sections_used
            console.print(Panel(
                f"[yellow]Sections used: {sections}[/yellow]\n"
                f"[yellow]Total tokens: {ctx.total_tokens:,}[/yellow]\n\n"
                f"{ctx.context_text[:300]}...",
                title=f"Context {i}: {ctx.metadata['doc_id']}",
                border_style="green"
            ))
    
    finally:
        # Cleanup
        shutil.rmtree(temp_dir)


def main():
    """Run all demos"""
    console.print("\n[bold magenta]" + "="*80 + "[/bold magenta]")
    console.print("[bold magenta]Context-Aware RAG System - Interactive Demo[/bold magenta]")
    console.print("[bold magenta]" + "="*80 + "[/bold magenta]\n")
    
    console.print("[dim]This demo showcases key features using local embeddings (no API key needed)[/dim]\n")
    
    demos = [
        ("Document Processing", demo_document_processing),
        ("Embedding Generation", demo_embedding),
        ("Vector Store & Retrieval", demo_vector_store),
        ("Context Expansion", demo_context_expansion)
    ]
    
    for name, demo_func in demos:
        try:
            demo_func()
        except Exception as e:
            console.print(f"\n[red]Error in {name}: {e}[/red]\n")
            import traceback
            traceback.print_exc()
    
    console.print("\n[bold magenta]" + "="*80 + "[/bold magenta]")
    console.print("[bold green]Demo completed! 🎉[/bold green]")
    console.print("[bold magenta]" + "="*80 + "[/bold magenta]\n")
    
    console.print("[dim]To use the full system with LLM augmentation:[/dim]")
    console.print("  1. Set OPENAI_API_KEY in .env file")
    console.print("  2. Run: python cli.py ingest -d sample_docs/ -v")
    console.print("  3. Run: python cli.py interactive -v\n")


if __name__ == '__main__':
    main()
