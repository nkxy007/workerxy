import asyncio
from typing import List, Dict, Any
from net_deepagent_cli.ui import TerminalUI
from net_deepagent_cli.commands import handle_command
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

async def interactive_loop(agent, args, ui: TerminalUI):
    """Main interactive loop"""
    ui.print_banner()
    
    # Session state - store as LangChain messages
    messages: List[Any] = []
    
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
            try:
                await handle_command(user_input, ui, messages)
            except EOFError:
                break
            continue
        
        # Add user message
        messages.append(HumanMessage(content=user_input))
        
        # Stream agent response
        await stream_agent_response(agent, messages, ui, args.auto_approve)

async def stream_agent_response(agent, messages, ui: TerminalUI, auto_approve: bool):
    """Stream agent response with real-time updates"""
    
    # In LangGraph/DeepAgent, the state is passed. 
    # We want to keep track of what's new.
    
    try:
        # We use a Live display for the assistant's growing message
        with ui.show_progress("Agent is thinking...") as progress:
            task = progress.add_task("Processing request...", total=None)
            
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
                                        ui.print_tool_call(tool_call["name"], tool_call["args"])
                                        
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
                                # We might want to show tool results if they are short
                                # ui.print_message(f"Tool {msg.name} returned result.", role="system")
                                pass
                                
                        last_message_count = len(all_messages)
                        # Update the messages history for the loop
                        messages.clear()
                        messages.extend(all_messages)

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
