import asyncio
from typing import List, Dict, Any
from net_deepagent_cli.ui import TerminalUI
from net_deepagent_cli.commands import handle_command
from net_deepagent_cli.automata import AutomataManager, handle_automata_ui
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from net_deepagent_cli.drift import TopicDriftDetector

async def interactive_loop(agent, args, ui: TerminalUI):
    """Main interactive loop"""
    ui.print_banner()
    
    # Initialize Automata Manager
    # We assume 'agent_name' is available in ui or args?
    # ui.agent_name is available.
    automata_manager = AutomataManager(ui.agent_name, agent)
    automata_manager.start()
    
    # Session state - store as LangChain messages
    messages: List[Any] = []
    
    # Initialize Drift Detector if flag is set
    drift_detector = TopicDriftDetector() if getattr(args, 'automatic_context_detection', False) else None
    if hasattr(agent, 'base_agent'):
        agent.drift_detector = drift_detector
    else:
        # In case it's not wrapped for some reason
        agent.drift_detector = drift_detector
    
    try:
        while True:
            # Get user input
            user_input = await ui.get_user_input()
            
            if user_input is None:
                # Ctrl+C or EOF
                ui.console.print("\n[yellow]Goodbye![/yellow]")
                break
            
            if not user_input:
                continue
                
            # Handle special commands
            if user_input.startswith("/"):
                if user_input.strip() == "/automata":
                    await handle_automata_ui(ui, automata_manager)
                    continue
                elif user_input.startswith("/automata "):
                     from net_deepagent_cli.automata import process_automata_command
                     arg_str = user_input[len("/automata "):].strip()
                     if arg_str:
                         await process_automata_command(automata_manager, arg_str, ui)
                         continue

                try:
                    await handle_command(user_input, ui, messages, agent=agent)
                except EOFError:
                    break
                continue
        
            # Add user message
            # Check for topic drift if enabled
            if drift_detector and messages:
                drift_info = await drift_detector.check_drift(messages, user_input)
                # Log detailed info as requested
                import logging
                logger = logging.getLogger("net_deepagent_cli")
                logger.info(f"Topic Drift Check: Similarity={drift_info['similarity']:.2f}, "
                            f"Current Topic='{drift_info['current_topic']}', "
                            f"New Input='{drift_info['new_topic']}'")
                
                if drift_info["drift"]:
                    if ui.prompt_new_session_drift():
                        await handle_command("/session new", ui, messages, agent=agent)
            
            messages.append(HumanMessage(content=user_input))
            
            # Stream agent response
            await stream_agent_response(agent, messages, ui, args.auto_approve)
            
            # Check for skill updates (if middleware is attached)
            if hasattr(agent, 'skill_learning_middleware'):
                from net_deepagent_cli.automata_skills_ui import handle_skill_updates
                await handle_skill_updates(agent.skill_learning_middleware, ui)
                
    except Exception as e:
        ui.console.print(f"[red]Error in interactive loop: {e}[/red]")
    finally:
        if 'automata_manager' in locals():
            automata_manager.stop()

async def stream_agent_response(agent, messages, ui: TerminalUI, auto_approve: bool):
    """Stream agent response with real-time updates"""
    
    # In LangGraph/DeepAgent, the state is passed. 
    # We want to keep track of what's new.
    
    try:
        # We use a Live display for the assistant's growing message
        with ui.show_progress("Agent is thinking...") as progress:
            task = progress.add_task("Processing request...", total=100)
            
            # Since we're using deepagents which wraps a langgraph, 
            # we'll use astream with the messages
            
            last_message_count = len(messages)
            
            async for chunk in agent.astream(
                {"messages": messages},
                stream_mode="values" # This gives the full state at each step
            ):
                if "messages" in chunk:
                    all_messages = chunk["messages"]
                    # If there are new messages, we process them
                    if len(all_messages) > last_message_count:
                        new_msgs = all_messages[last_message_count:]
                        for msg in new_msgs:
                            if isinstance(msg, AIMessage):
                                # Update token counts if available in metadata
                                if hasattr(msg, "response_metadata") and msg.response_metadata:
                                    usage = msg.response_metadata.get("token_usage", {})
                                    if usage:
                                        total = usage.get("total_tokens", 0)
                                        if total:
                                            ui.total_tokens += total

                                if msg.content:
                                    ui.print_message(msg.content, role="assistant")
                                
                                if hasattr(msg, "tool_calls") and msg.tool_calls:
                                    for tool_call in msg.tool_calls:
                                        # Update progress based on tool
                                        tool_name = tool_call["name"]
                                        if tool_name.startswith("communicate_with_"):
                                            # Derive agent name (e.g., communicate_with_dns_deepagent -> dns-deepagent)
                                            agent_name = tool_name.replace("communicate_with_", "").replace("_", "-")
                                            progress.update(task, description=f"[bold cyan]Waiting for {agent_name}...[/bold cyan]")
                                        else:
                                            progress.update(task, description=f"[bold yellow]Executing {tool_name}...[/bold yellow]")
                                            
                                        ui.print_tool_call(tool_name, tool_call["args"])
                                        
                                        # Human-in-the-loop approval
                                        if not auto_approve and requires_approval(tool_call["name"]):
                                            approval = ui.request_approval(
                                                tool_call["name"], 
                                                str(tool_call["args"])
                                            )
                                            if approval == "reject":
                                                # How to handle rejection in LangGraph?
                                                # One way is to inject a "user rejected" message or error.
                                                # For now, we'll just log it. In a real implementation, 
                                                # we'd need to stop the execution or send a ToolMessage with failure.
                                                ui.print_message(f"Tool {tool_call['name']} was rejected by user.", role="system")
                                            elif approval == "edit":
                                                ui.print_message("Editing tool calls not yet implemented in this MVP.", role="system")
                            
                            elif isinstance(msg, ToolMessage):
                                # Tool has returned, update progress
                                progress.update(task, description="[bold green]Processing tool output...[/bold green]")
                                pass
                            
                            elif isinstance(msg, AIMessage) and msg.content:
                                # Final response is being generated
                                progress.update(task, description="[bold blue]Finalizing response...[/bold blue]")
                                ui.print_message(msg.content, role="assistant")
                                
                        last_message_count = len(all_messages)
                        # Update the messages history for the loop
                        messages.clear()
                        messages.extend(all_messages)
                        
                        # Pass new messages to skill learning middleware
                        if hasattr(agent, 'skill_learning_middleware'):
                            for msg in new_msgs:
                                # Convert LangChain message to simple dict for processing
                                content = msg.content if msg.content else ""
                                if isinstance(msg, AIMessage):
                                    role = "assistant"
                                elif isinstance(msg, ToolMessage):
                                    role = "tool"
                                    # For tool messages, we might want to include tool name if available
                                    # But process_message handles raw text anyway
                                else:
                                    role = "user"
                                
                                agent.skill_learning_middleware.process_message({'role': role, 'content': content})

    except Exception as e:
        ui.print_message(f"An error occurred: {str(e)}", role="error")
        import traceback
        ui.console.print(f"[dim]{traceback.format_exc()}[/dim]")

def requires_approval(tool_name: str) -> bool:
    """Check if tool requires human approval"""
    # Sensitive tools that should be approved by default
    sensitive_tools = [
        "Unified_SSH_configuration_tool", 
        "ssh_tool", 
        "write_file", 
        "delete_file", 
        "aws_tool", 
        "azure_tool", 
        "gcp_tool"
    ]
    return tool_name in sensitive_tools
