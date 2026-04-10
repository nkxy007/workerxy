"""
Skills Middleware - Integrates skill update detection into the agent pipeline

This middleware:
- Passively monitors agent conversations
- Detects skill update opportunities
- Queues update proposals
- Requests user approval
- Applies approved updates
"""

import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

from utils.skill_updater import SkillUpdateDetector
from utils.skill_writer import SkillWriter

logger = logging.getLogger(__name__)


class SkillLearningMiddleware:
    """Middleware for automatic skill updates via passive monitoring"""
    
    def __init__(self, skills_dir: str = "skills"):
        """
        Initialize the skill learning middleware
        
        Args:
            skills_dir: Path to the skills directory
        """
        self.skills_dir = Path(skills_dir)
        self.detector = SkillUpdateDetector(str(self.skills_dir))
        self.pending_updates: Dict[str, List[Dict]] = {}  # skill_name -> list of proposals
        self.conversation_buffer = []  # Buffer recent conversation context
        
        logger.info(f"SkillLearningMiddleware initialized with {len(self.detector.skills)} skills in {self.skills_dir}")
    
    def process_message(self, message: Dict[str, Any]) -> None:
        """
        Process a message from the agent conversation
        
        Args:
            message: Message dict with 'role' and 'content'
        """
        # Add to conversation buffer
        content = str(message.get('content', ''))
        self.conversation_buffer.append(content)
        
        # Keep buffer size manageable (last 10 messages)
        if len(self.conversation_buffer) > 10:
            self.conversation_buffer.pop(0)
        
        # Analyze for skill updates
        self._analyze_for_updates(content)
    
    def process_tool_output(self, tool_name: str, tool_output: str) -> None:
        """
        Process tool output for skill update opportunities
        
        Args:
            tool_name: Name of the tool that was executed
            tool_output: Output from the tool
        """
        logger.debug(f"Processing tool output from {tool_name}")
        
        # Tool outputs are often rich in network information
        self._analyze_for_updates(tool_output)
    
    def _analyze_for_updates(self, context: str) -> None:
        """
        Analyze context for potential skill updates
        
        Args:
            context: Text to analyze
        """
        if not context or len(context.strip()) == 0:
            return
        
        # Find relevant skills
        relevant_skills = self.detector.match_skills_to_context(context)
        
        if not relevant_skills:
            return
        
        logger.info(f"Found {len(relevant_skills)} relevant skills: {relevant_skills}")
        
        # Check each relevant skill for updates
        for skill_name in relevant_skills:
            should_update, proposals = self.detector.should_update(context, skill_name)
            
            if should_update and proposals:
                # Add to pending updates
                if skill_name not in self.pending_updates:
                    self.pending_updates[skill_name] = []
                
                for proposal in proposals:
                    # Check if similar proposal already exists
                    if not self._is_duplicate_proposal(skill_name, proposal):
                        self.pending_updates[skill_name].append(proposal)
                        logger.info(f"Queued update for {skill_name}: {proposal['reason']}")
    
    def _is_duplicate_proposal(self, skill_name: str, new_proposal: Dict) -> bool:
        """Check if a similar proposal already exists"""
        if skill_name not in self.pending_updates:
            return False
        
        for existing in self.pending_updates[skill_name]:
            if existing['type'] == new_proposal['type']:
                # Check if data is similar
                if existing['data'] == new_proposal['data']:
                    return True
        
        return False
    
    def get_pending_updates(self, skill_name: Optional[str] = None) -> Dict[str, List[Dict]]:
        """
        Get pending updates for a skill or all skills
        
        Args:
            skill_name: Optional skill name to filter by
        
        Returns:
            Dict of skill_name -> list of proposals
        """
        if skill_name:
            return {skill_name: self.pending_updates.get(skill_name, [])}
        return self.pending_updates
    
    def apply_updates(self, skill_name: str, approved_indices: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Apply pending updates to a skill
        
        Args:
            skill_name: Name of the skill to update
            approved_indices: Indices of proposals to apply (None = all)
        
        Returns:
            Dict with results: {success: bool, applied: int, failed: int, errors: []}
        """
        if skill_name not in self.pending_updates:
            return {'success': False, 'error': 'No pending updates for this skill'}
        
        proposals = self.pending_updates[skill_name]
        
        if not proposals:
            return {'success': False, 'error': 'No pending updates'}
        
        # Determine which proposals to apply
        if approved_indices is None:
            to_apply = proposals
        else:
            to_apply = [proposals[i] for i in approved_indices if i < len(proposals)]
        
        # Get skill path
        skill_data = self.detector.skills.get(skill_name)
        if not skill_data:
            return {'success': False, 'error': f'Skill {skill_name} not found'}
        
        skill_path = skill_data['path']
        writer = SkillWriter(str(skill_path))
        
        # Apply updates
        applied = 0
        failed = 0
        errors = []
        
        for proposal in to_apply:
            try:
                success = False
                
                if proposal['type'] == 'network_device':
                    success = writer.add_network_device(proposal['data'])
                elif proposal['type'] == 'vlan':
                    success = writer.add_vlan(proposal['data'])
                elif proposal['type'] == 'monitoring_tool':
                    success = writer.add_monitoring_tool(proposal['data'])
                
                if success:
                    applied += 1
                    logger.info(f"Applied update: {proposal['reason']}")
                else:
                    failed += 1
                    errors.append(f"Failed to apply: {proposal['reason']}")
            
            except Exception as e:
                failed += 1
                errors.append(f"Error applying {proposal['reason']}: {str(e)}")
                logger.error(f"Error applying update: {e}")
        
        # Clear applied updates
        if approved_indices is None:
            self.pending_updates[skill_name] = []
        else:
            # Remove applied proposals
            remaining = [p for i, p in enumerate(proposals) if i not in approved_indices]
            self.pending_updates[skill_name] = remaining
        
        return {
            'success': applied > 0,
            'applied': applied,
            'failed': failed,
            'errors': errors
        }
    
    def reject_updates(self, skill_name: str, rejected_indices: Optional[List[int]] = None) -> None:
        """
        Reject pending updates
        
        Args:
            skill_name: Name of the skill
            rejected_indices: Indices to reject (None = all)
        """
        if skill_name not in self.pending_updates:
            return
        
        if rejected_indices is None:
            # Reject all
            self.pending_updates[skill_name] = []
            logger.info(f"Rejected all pending updates for {skill_name}")
        else:
            # Reject specific indices
            proposals = self.pending_updates[skill_name]
            remaining = [p for i, p in enumerate(proposals) if i not in rejected_indices]
            self.pending_updates[skill_name] = remaining
            logger.info(f"Rejected {len(rejected_indices)} updates for {skill_name}")
    
    def format_update_summary(self, skill_name: Optional[str] = None) -> str:
        """
        Format a human-readable summary of pending updates
        
        Args:
            skill_name: Optional skill to filter by
        
        Returns:
            Formatted string summary
        """
        pending = self.get_pending_updates(skill_name)
        
        if not pending or all(len(updates) == 0 for updates in pending.values()):
            return "No pending updates."
        
        lines = []
        total_updates = 0
        
        for skill, proposals in pending.items():
            if not proposals:
                continue
            
            lines.append(f"\n**{skill}** ({len(proposals)} update{'s' if len(proposals) > 1 else ''}):")
            
            for i, proposal in enumerate(proposals):
                confidence = proposal.get('confidence', 0)
                reason = proposal.get('reason', 'Unknown')
                lines.append(f"  {i+1}. {reason} (confidence: {confidence}%)")
                total_updates += 1
        
        if not lines:
            return "No pending updates."
        
        header = f"Found {total_updates} pending update{'s' if total_updates > 1 else ''} across {len(pending)} skill{'s' if len(pending) > 1 else ''}:"
        return header + '\n' + '\n'.join(lines)
    
    def clear_all_pending(self) -> None:
        """Clear all pending updates"""
        self.pending_updates = {}
        logger.info("Cleared all pending updates")

    def get_all_pending_updates(self) -> Dict[str, List[Dict]]:
        """
        Get all pending updates for all skills
        
        Returns:
            Dict mapping skill_name to list of proposals
        """
        # Filter out empty lists
        return {k: v for k, v in self.pending_updates.items() if v}

    def apply_all_updates(self) -> Dict[str, Dict]:
        """
        Apply all pending updates across all skills
        
        Returns:
            Dict mapping skill_name to result dict
        """
        results = {}
        # Iterate over a copy of keys since we modify the dict
        # We need to filter for skills that actually have updates
        skills_with_updates = [k for k, v in self.pending_updates.items() if v]
        
        for skill_name in skills_with_updates:
            results[skill_name] = self.apply_updates(skill_name)
            
        return results

    def clear_updates(self) -> None:
        """Alias for clear_all_pending for compatibility"""
        self.clear_all_pending()


# Global instance for easy access
_skill_learning_middleware_instance: Optional[SkillLearningMiddleware] = None


def get_skill_learning_middleware(skills_dir: str = "skills") -> SkillLearningMiddleware:
    """
    Get or create the global skill learning middleware instance
    
    Args:
        skills_dir: Path to skills directory
    
    Returns:
        SkillLearningMiddleware instance
    """
    global _skill_learning_middleware_instance
    
    if _skill_learning_middleware_instance is None:
        _skill_learning_middleware_instance = SkillLearningMiddleware(skills_dir)
    
    return _skill_learning_middleware_instance
