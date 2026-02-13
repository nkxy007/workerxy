"""
Command-line interface for Context-Aware RAG
"""
import argparse
import json
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table

from rag_system import ContextRAG
from config import get_config


console = Console()


def ingest_command(args):
    """Handle ingest command"""
    # Initialize RAG system
    config = get_config(verbose=args.verbose)
    rag = ContextRAG(config)
    
    # Get file paths
    file_paths = []
    if args.file:
        file_paths = [args.file]
    elif args.directory:
        directory = Path(args.directory)
        extensions = {'.pdf', '.docx', '.md', '.txt', '.py', '.js', '.java', '.cpp', '.c'}
        file_paths = [
            str(f) for f in directory.rglob('*') 
            if f.suffix.lower() in extensions
        ]
    
    if not file_paths:
        console.print("[red]No files to ingest[/red]")
        return
    
    console.print(f"\n[bold cyan]Ingesting {len(file_paths)} files...[/bold cyan]")
    
    # Ingest documents
    results = rag.ingest_documents(file_paths)
    
    # Display results
    table = Table(title="Ingestion Results")
    table.add_column("File", style="cyan")
    table.add_column("Doc ID", style="magenta")
    table.add_column("Type", style="green")
    table.add_column("Chunks", style="yellow")
    table.add_column("Status", style="bold")
    
    for result in results:
        if 'error' in result:
            table.add_row(
                result['file_path'],
                "-",
                "-",
                "-",
                "[red]Error[/red]"
            )
        else:
            table.add_row(
                result['file_path'],
                result['doc_id'],
                result['doc_type'],
                str(result['num_chunks']),
                "[green]Success[/green]"
            )
    
    console.print(table)
    
    # Show stats
    stats = rag.get_stats()
    console.print(f"\n[bold green]Total chunks in database: {stats['total_chunks']}[/bold green]")


def query_command(args):
    """Handle query command"""
    # Initialize RAG system
    config_kwargs = {}
    
    if args.top_k:
        config_kwargs['retrieval'] = {'top_k': args.top_k}
    if args.context_window:
        if 'retrieval' not in config_kwargs:
            config_kwargs['retrieval'] = {}
        config_kwargs['retrieval']['context_window'] = args.context_window
    if args.model:
        config_kwargs['llm'] = {'model': args.model}
    
    config_kwargs['verbose'] = args.verbose
    
    config = get_config(**config_kwargs)
    rag = ContextRAG(config)
    
    # Check if database has content
    stats = rag.get_stats()
    if stats['total_chunks'] == 0:
        console.print("[red]Database is empty. Please ingest documents first.[/red]")
        return
    
    # Query
    console.print(f"\n[bold cyan]Question:[/bold cyan] {args.query}")
    
    result = rag.query(args.query, retrieve_only=args.retrieve_only)
    
    # Display results
    if args.retrieve_only:
        # Show retrieval results
        console.print(f"\n[bold green]Retrieved {len(result['contexts'])} contexts[/bold green]")
        console.print(f"[yellow]Total tokens: {result['total_tokens']:,}[/yellow]\n")
        
        for i, ctx in enumerate(result['contexts'], 1):
            location = (f"Pages {ctx['pages']}" if ctx['pages'] 
                       else f"Sections {ctx['sections']}")
            
            console.print(Panel(
                ctx['text'][:500] + "..." if len(ctx['text']) > 500 else ctx['text'],
                title=f"Context {i}: {ctx['metadata']['doc_id']} ({location})",
                border_style="cyan"
            ))
    else:
        # Show answer with citations
        console.print("\n" + "="*80)
        console.print(Panel(
            Markdown(result['answer']),
            title="Answer",
            border_style="green",
            padding=(1, 2)
        ))
        console.print("="*80)
        
        # Show sources
        if result.get('sources'):
            console.print(f"\n[bold cyan]Sources ({len(result['sources'])}):[/bold cyan]")
            for src in result['sources']:
                doc_id = src['doc_id']
                location = (f"pages {src['page_range']}" if 'pages' in src 
                           else f"sections {src['section_range']}")
                score = src['match_score']
                console.print(f"  • {doc_id} ({location}) - Score: {score:.3f}")
        
        # Show usage
        if 'usage' in result:
            console.print(f"\n[dim]Tokens used: {result['usage']['total_tokens']:,}[/dim]")
        
        # Save to file if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(result, f, indent=2)
            console.print(f"\n[green]Results saved to {args.output}[/green]")


def interactive_mode(args):
    """Interactive query mode"""
    config = get_config(verbose=args.verbose)
    rag = ContextRAG(config)
    
    # Check database
    stats = rag.get_stats()
    if stats['total_chunks'] == 0:
        console.print("[red]Database is empty. Please ingest documents first.[/red]")
        return
    
    console.print("\n[bold cyan]Context-Aware RAG - Interactive Mode[/bold cyan]")
    console.print("[dim]Type 'exit' or 'quit' to exit[/dim]\n")
    console.print(f"[green]Database contains {stats['total_chunks']} chunks[/green]")
    console.print(f"[yellow]Model: {stats['config']['llm_model']}[/yellow]\n")
    
    while True:
        try:
            # Get query
            query = console.input("\n[bold cyan]Question:[/bold cyan] ").strip()
            
            if query.lower() in ['exit', 'quit', 'q']:
                console.print("\n[yellow]Goodbye![/yellow]")
                break
            
            if not query:
                continue
            
            # Process query
            result = rag.query(query)
            
            # Display answer
            console.print("\n" + "="*80)
            console.print(Panel(
                Markdown(result['answer']),
                title="Answer",
                border_style="green"
            ))
            console.print("="*80)
            
            # Show sources
            if result.get('sources'):
                console.print(f"\n[dim]Sources: {len(result['sources'])} | " +
                            f"Tokens: {result.get('context_tokens', 0):,}[/dim]")
        
        except KeyboardInterrupt:
            console.print("\n\n[yellow]Goodbye![/yellow]")
            break
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")


def stats_command(args):
    """Show system statistics"""
    config = get_config(verbose=False)
    rag = ContextRAG(config)
    
    stats = rag.get_stats()
    
    # Display stats
    console.print("\n[bold cyan]Context-Aware RAG Statistics[/bold cyan]\n")
    
    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="yellow")
    
    table.add_row("Total Chunks", f"{stats['total_chunks']:,}")
    table.add_row("Embedding Model", stats['config']['embedding_model'])
    table.add_row("LLM Model", stats['config']['llm_model'])
    table.add_row("Top K", str(stats['config']['top_k']))
    table.add_row("Context Window", f"±{stats['config']['context_window']}")
    table.add_row("Max Context Tokens", f"{stats['config']['max_context_tokens']:,}")
    
    console.print(table)


def clear_command(args):
    """Clear the database"""
    config = get_config(verbose=False)
    rag = ContextRAG(config)
    
    if not args.force:
        confirm = console.input("\n[yellow]Are you sure you want to clear the database? (yes/no):[/yellow] ")
        if confirm.lower() != 'yes':
            console.print("[cyan]Cancelled[/cyan]")
            return
    
    rag.clear_database()
    console.print("[green]Database cleared successfully[/green]")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Context-Aware RAG with Smart Context Expansion",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Enable verbose output')
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Ingest command
    ingest_parser = subparsers.add_parser('ingest', help='Ingest documents')
    ingest_parser.add_argument('-f', '--file', help='Single file to ingest')
    ingest_parser.add_argument('-d', '--directory', help='Directory to ingest (recursive)')
    
    # Query command
    query_parser = subparsers.add_parser('query', help='Query the RAG system')
    query_parser.add_argument('query', help='Question to ask')
    query_parser.add_argument('-k', '--top-k', type=int, help='Number of top results')
    query_parser.add_argument('-w', '--context-window', type=int, help='Context window size')
    query_parser.add_argument('-m', '--model', help='LLM model to use')
    query_parser.add_argument('-r', '--retrieve-only', action='store_true',
                             help='Only retrieve context, don\'t generate answer')
    query_parser.add_argument('-o', '--output', help='Save results to JSON file')
    
    # Interactive command
    interactive_parser = subparsers.add_parser('interactive', help='Interactive query mode')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show system statistics')
    
    # Clear command
    clear_parser = subparsers.add_parser('clear', help='Clear the database')
    clear_parser.add_argument('--force', action='store_true', help='Skip confirmation')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Execute command
    commands = {
        'ingest': ingest_command,
        'query': query_command,
        'interactive': interactive_mode,
        'stats': stats_command,
        'clear': clear_command
    }
    
    commands[args.command](args)


if __name__ == '__main__':
    main()
