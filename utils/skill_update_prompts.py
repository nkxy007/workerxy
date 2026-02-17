"""
Skill Update Prompts - Standardized prompts for skill update interactions

This module provides user interaction patterns for skill updates.
"""

from typing import Dict, List, Optional


def format_update_proposal(skill_name: str, proposals: List[Dict]) -> str:
    """
    Format update proposals for user review
    
    Args:
        skill_name: Name of the skill
        proposals: List of update proposals
    
    Returns:
        Formatted string for user
    """
    if not proposals:
        return f"No pending updates for {skill_name}."
    
    lines = [f"\n📝 **Skill Update Proposal: {skill_name}**\n"]
    lines.append(f"Found {len(proposals)} potential update{'s' if len(proposals) > 1 else ''}:\n")
    
    for i, proposal in enumerate(proposals, 1):
        confidence = proposal.get('confidence', 0)
        reason = proposal.get('reason', 'Unknown')
        data = proposal.get('data', {})
        
        lines.append(f"{i}. {reason}")
        lines.append(f"   Confidence: {confidence}%")
        
        # Show key details
        if proposal['type'] == 'network_device':
            if 'hostname' in data:
                lines.append(f"   Hostname: {data['hostname']}")
            if 'ip_address' in data:
                lines.append(f"   IP: {data['ip_address']}")
            if 'model' in data:
                lines.append(f"   Model: {data['model']}")
        
        elif proposal['type'] == 'vlan':
            if 'vlan_id' in data:
                lines.append(f"   VLAN ID: {data['vlan_id']}")
            if 'subnet' in data:
                lines.append(f"   Subnet: {data['subnet']}")
        
        elif proposal['type'] == 'monitoring_tool':
            if 'tool_name' in data:
                lines.append(f"   Tool: {data['tool_name']}")
            if 'url' in data:
                lines.append(f"   URL: {data['url']}")
        
        lines.append("")  # Blank line between proposals
    
    return '\n'.join(lines)


def format_batch_update_summary(pending_updates: Dict[str, List[Dict]]) -> str:
    """
    Format a summary of pending updates across multiple skills
    
    Args:
        pending_updates: Dict of skill_name -> list of proposals
    
    Returns:
        Formatted summary string
    """
    if not pending_updates or all(len(updates) == 0 for updates in pending_updates.values()):
        return "No pending skill updates."
    
    total_updates = sum(len(proposals) for proposals in pending_updates.values())
    skill_count = len([s for s, p in pending_updates.items() if p])
    
    lines = [f"\n✨ **Task Complete!**\n"]
    lines.append(f"I discovered {total_updates} update{'s' if total_updates > 1 else ''} for {skill_count} skill{'s' if skill_count > 1 else ''}:\n")
    
    for skill_name, proposals in pending_updates.items():
        if not proposals:
            continue
        
        lines.append(f"**{skill_name}** ({len(proposals)} update{'s' if len(proposals) > 1 else ''}):")
        
        for i, proposal in enumerate(proposals, 1):
            reason = proposal.get('reason', 'Unknown')
            confidence = proposal.get('confidence', 0)
            lines.append(f"  {i}. {reason} ({confidence}% confidence)")
        
        lines.append("")  # Blank line between skills
    
    lines.append("\nWould you like to apply these updates?")
    lines.append("Options: [Y]es / [N]o / [R]eview individual updates")
    
    return '\n'.join(lines)


def format_apply_result(result: Dict) -> str:
    """
    Format the result of applying updates
    
    Args:
        result: Result dict from apply_updates
    
    Returns:
        Formatted result string
    """
    if not result.get('success'):
        error = result.get('error', 'Unknown error')
        return f"❌ Failed to apply updates: {error}"
    
    applied = result.get('applied', 0)
    failed = result.get('failed', 0)
    
    lines = [f"✅ Successfully applied {applied} update{'s' if applied > 1 else ''}!"]
    
    if failed > 0:
        lines.append(f"⚠️  {failed} update{'s' if failed > 1 else ''} failed:")
        for error in result.get('errors', []):
            lines.append(f"  - {error}")
    
    return '\n'.join(lines)


def prompt_immediate_update(skill_name: str, reason: str, confidence: int) -> str:
    """
    Prompt for immediate update during task execution
    
    Args:
        skill_name: Name of the skill
        reason: Reason for the update
        confidence: Confidence score
    
    Returns:
        Prompt string
    """
    return f"""
🔍 **Skill Update Detected**

I discovered new information for the **{skill_name}** skill:
- {reason}
- Confidence: {confidence}%

Would you like me to add this to the skill?
[Y]es / [N]o / [L]ater (queue for end of task)
"""


def prompt_manual_update_request(skill_name: str) -> str:
    """
    Prompt when user manually requests skill update
    
    Args:
        skill_name: Name of the skill
    
    Returns:
        Prompt string
    """
    return f"""
🔍 **Analyzing recent conversations for {skill_name} updates...**

Please wait while I extract relevant information...
"""


def prompt_no_updates_found(skill_name: str) -> str:
    """
    Message when no updates are found
    
    Args:
        skill_name: Name of the skill
    
    Returns:
        Message string
    """
    return f"""
ℹ️  No new information found for **{skill_name}** in recent conversations.

The skill appears to be up-to-date based on our recent work.
"""


def prompt_obsolete_removal(skill_name: str, entry_description: str) -> str:
    """
    Prompt for removing obsolete information
    
    Args:
        skill_name: Name of the skill
        entry_description: Description of the entry to remove
    
    Returns:
        Prompt string
    """
    return f"""
🗑️  **Obsolete Information Detected**

The **{skill_name}** skill contains:
- {entry_description}

This appears to be outdated or replaced. Should I remove it?
[Y]es / [N]o / [K]eep both
"""


def format_skill_list(skills: Dict[str, Dict]) -> str:
    """
    Format list of available skills
    
    Args:
        skills: Dict of skill_name -> skill_data
    
    Returns:
        Formatted list
    """
    if not skills:
        return "No skills found."
    
    lines = ["\n📚 **Available Skills:**\n"]
    
    for skill_name, skill_data in skills.items():
        config = skill_data.get('config', {})
        skill_config = config.get('skill', {})
        
        auto_update = skill_config.get('auto_update_enabled', False)
        update_policy = skill_config.get('update_policy', 'manual-only')
        
        status = "🟢 Auto" if auto_update else "🔵 Manual"
        
        lines.append(f"  {status} **{skill_name}**")
        lines.append(f"      Policy: {update_policy}")
        lines.append("")
    
    return '\n'.join(lines)
