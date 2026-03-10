"""
Handle UI interactions for skill updates
"""
from net_deepagent_cli.ui import TerminalUI
from utils.skill_update_prompts import format_batch_update_summary, format_apply_result

from typing import Optional

async def handle_skill_updates(middleware, ui: TerminalUI, skill_name: Optional[str] = None):
    """
    Check for pending skill updates and prompt user
    
    Args:
        middleware: SkillLearningMiddleware instance
        ui: TerminalUI instance
        skill_name: Optional skill name to filter by
    """
    # Get pending updates
    if skill_name:
        pending = middleware.get_pending_updates(skill_name)
    else:
        pending = middleware.get_all_pending_updates()
    
    if not pending:
        return
        
    # Format summary
    summary = format_batch_update_summary(pending)
    ui.print_message(summary, role="system")
    
    # helper for asking
    response = await ui.prompt_simple("Apply these updates? [Y]es / [N]o / [R]eview details: ")
    
    if not response:
        return
        
    choice = response.lower().strip()
    
    if choice.startswith('y'):
        ui.print_message("Applying updates...", role="system")
        results = middleware.apply_all_updates()
        
        for skill_name, result in results.items():
            formatted = format_apply_result(result)
            ui.print_message(f"**{skill_name}**: {formatted}", role="system")
            
    elif choice.startswith('r'):
        # Review individual updates
        for skill_name, proposals in pending.items():
            if not proposals:
                continue
                
            ui.print_message(f"\nupdates for **{skill_name}**:", role="system")
            for i, p in enumerate(proposals, 1):
                ui.print_message(f"{i}. {p['reason']} ({p['confidence']}%)", role="system")
                
            sub_choice = await ui.prompt_simple(f"Apply updates for {skill_name}? [Y]es / [N]o: ")
            if sub_choice and sub_choice.lower().startswith('y'):
                result = middleware.apply_updates(skill_name)
                ui.print_message(format_apply_result(result), role="system")
    
    else:
        ui.print_message("Updates discarded.", role="system")
        middleware.clear_updates()
