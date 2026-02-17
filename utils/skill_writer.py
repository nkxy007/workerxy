"""
Skill Writer - Handles safe modification of SKILL.md files

This module provides utilities for:
- Parsing SKILL.md structure
- Adding new information to appropriate sections
- Updating metadata and changelog
- Creating backups and supporting rollback
- Preventing duplicate entries
"""

import os
import re
import yaml
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class SkillWriter:
    """Manages safe updates to SKILL.md files"""
    
    def __init__(self, skill_path: str):
        """
        Initialize SkillWriter for a specific skill
        
        Args:
            skill_path: Path to the skill directory (e.g., skills/network-design-document)
        """
        self.skill_path = Path(skill_path)
        self.skill_file = self.skill_path / "SKILL.md"
        self.config_file = self.skill_path / "skill_config.yaml"
        self.backup_dir = self.skill_path / ".skill_backups"
        
        # Load configuration
        self.config = self._load_config()
        
        # Ensure backup directory exists
        if self.config.get('backup', {}).get('enabled', True):
            self.backup_dir.mkdir(exist_ok=True)
    
    def _load_config(self) -> Dict:
        """Load skill configuration from YAML"""
        if not self.config_file.exists():
            logger.warning(f"Config file not found: {self.config_file}")
            return {}
        
        with open(self.config_file, 'r') as f:
            return yaml.safe_load(f) or {}
    
    def _create_backup(self) -> Optional[Path]:
        """Create a backup of the current SKILL.md"""
        if not self.skill_file.exists():
            return None
        
        if not self.config.get('backup', {}).get('enabled', True):
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"SKILL_{timestamp}.md"
        
        shutil.copy2(self.skill_file, backup_file)
        logger.info(f"Created backup: {backup_file}")
        
        # Clean old backups
        self._cleanup_old_backups()
        
        return backup_file
    
    def _cleanup_old_backups(self):
        """Remove old backups beyond max_backups limit"""
        max_backups = self.config.get('backup', {}).get('max_backups', 10)
        
        backups = sorted(self.backup_dir.glob("SKILL_*.md"), reverse=True)
        
        for old_backup in backups[max_backups:]:
            old_backup.unlink()
            logger.info(f"Removed old backup: {old_backup}")
    
    def _parse_frontmatter(self, content: str) -> Tuple[Dict, str]:
        """
        Parse YAML frontmatter from SKILL.md
        
        Returns:
            (frontmatter_dict, remaining_content)
        """
        if not content.startswith('---'):
            return {}, content
        
        parts = content.split('---', 2)
        if len(parts) < 3:
            return {}, content
        
        try:
            frontmatter = yaml.safe_load(parts[1]) or {}
            remaining = parts[2]
            return frontmatter, remaining
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse frontmatter: {e}")
            return {}, content
    
    def _update_frontmatter(self, frontmatter: Dict) -> Dict:
        """Update frontmatter metadata"""
        if 'metadata' not in frontmatter:
            frontmatter['metadata'] = {}
        
        frontmatter['metadata']['last-updated'] = datetime.now().strftime("%Y-%m-%d")
        
        # Increment total updates
        total_updates = frontmatter['metadata'].get('total-updates', 0)
        frontmatter['metadata']['total-updates'] = total_updates + 1
        
        return frontmatter
    
    def _find_section(self, content: str, section_name: str) -> Optional[Tuple[int, int]]:
        """
        Find the start and end positions of a section
        
        Returns:
            (start_pos, end_pos) or None if not found
        """
        # Match section headers (## or ### Section Name)
        pattern = rf'^###?\s+.*{re.escape(section_name)}.*$'
        
        lines = content.split('\n')
        start_line = None
        header_level = None
        
        for i, line in enumerate(lines):
            if re.match(pattern, line, re.IGNORECASE):
                start_line = i
                # Determine header level (## vs ###)
                header_level = 3 if line.startswith('###') else 2
                break
        
        if start_line is None:
            return None
        
        # Find the end of this section (next header of same or higher level, or end of file)
        end_line = len(lines)
        for i in range(start_line + 1, len(lines)):
            # Check if this is a header of same or higher level
            if header_level == 2 and lines[i].startswith('## '):
                end_line = i
                break
            elif header_level == 3 and (lines[i].startswith('## ') or lines[i].startswith('### ')):
                end_line = i
                break
        
        return start_line, end_line
    
    def _check_duplicate(self, content: str, identifier: str) -> bool:
        """Check if an entry already exists (simple substring check)"""
        return identifier.lower() in content.lower()
    
    def add_network_device(self, device_info: Dict) -> bool:
        """
        Add a network device to the Infrastructure Components section
        
        Args:
            device_info: Dict with keys: hostname, ip_address, model, role, device_type
        
        Returns:
            True if added successfully, False otherwise
        """
        if not self.skill_file.exists():
            logger.error(f"SKILL.md not found: {self.skill_file}")
            return False
        
        # Create backup
        self._create_backup()
        
        # Read current content
        with open(self.skill_file, 'r') as f:
            content = f.read()
        
        # Check for duplicates
        hostname = device_info.get('hostname', '')
        if self._check_duplicate(content, hostname):
            logger.info(f"Device {hostname} already exists in skill")
            return False
        
        # Parse frontmatter
        frontmatter, body = self._parse_frontmatter(content)
        
        # Determine section based on device type
        device_type = device_info.get('device_type', 'other').lower()
        section_map = {
            'router': 'Core Routers',
            'switch': 'Switches',
            'firewall': 'Firewalls',
            'load_balancer': 'Load Balancers',
            'other': 'Other Network Devices',
        }
        section_name = section_map.get(device_type, 'Other Network Devices')
        
        # Find the section
        section_pos = self._find_section(body, section_name)
        if not section_pos:
            logger.error(f"Section '{section_name}' not found in SKILL.md")
            return False
        
        start_line, end_line = section_pos
        lines = body.split('\n')
        
        # Create device entry
        device_entry = f"""
- **Hostname**: `{device_info.get('hostname', 'Unknown')}`
- **IP Address**: `{device_info.get('ip_address', 'Unknown')}`
- **Model**: {device_info.get('model', 'Unknown')}
- **Role**: {device_info.get('role', 'Unknown')}
- **Discovered**: {datetime.now().strftime("%Y-%m-%d")}
"""
        
        # Find where to insert (after "Discovered Devices: X" line)
        insert_line = start_line + 1
        for i in range(start_line, end_line):
            if 'Discovered Devices:' in lines[i]:
                # Update count
                current_count = int(re.search(r'\d+', lines[i]).group())
                lines[i] = f"**Discovered Devices**: {current_count + 1}"
                insert_line = i + 1
                break
        
        # Insert the device entry
        lines.insert(insert_line, device_entry)
        
        # Update frontmatter
        frontmatter = self._update_frontmatter(frontmatter)
        
        # Add to changelog
        changelog_entry = f"- **{datetime.now().strftime('%Y-%m-%d')}**: Added {device_type} `{hostname}` ({device_info.get('ip_address', 'N/A')})"
        lines = self._add_to_changelog(lines, changelog_entry)
        
        # Reconstruct content
        new_body = '\n'.join(lines)
        new_content = f"---\n{yaml.dump(frontmatter, default_flow_style=False)}---{new_body}"
        
        # Write back
        with open(self.skill_file, 'w') as f:
            f.write(new_content)
        
        logger.info(f"Added device {hostname} to {section_name}")
        return True
    
    def add_vlan(self, vlan_info: Dict) -> bool:
        """
        Add VLAN configuration to the IP Addressing & VLANs section
        
        Args:
            vlan_info: Dict with keys: vlan_id, name, subnet, purpose
        """
        if not self.skill_file.exists():
            return False
        
        self._create_backup()
        
        with open(self.skill_file, 'r') as f:
            content = f.read()
        
        # Check for duplicates
        vlan_id = vlan_info.get('vlan_id', '')
        if self._check_duplicate(content, f"VLAN {vlan_id}"):
            logger.info(f"VLAN {vlan_id} already exists")
            return False
        
        frontmatter, body = self._parse_frontmatter(content)
        section_pos = self._find_section(body, 'VLAN Configuration')
        
        if not section_pos:
            return False
        
        start_line, end_line = section_pos
        lines = body.split('\n')
        
        vlan_entry = f"""
- **VLAN ID**: {vlan_info.get('vlan_id', 'Unknown')}
- **Name**: {vlan_info.get('name', 'Unknown')}
- **Subnet**: `{vlan_info.get('subnet', 'Unknown')}`
- **Purpose**: {vlan_info.get('purpose', 'Unknown')}
- **Discovered**: {datetime.now().strftime("%Y-%m-%d")}
"""
        
        # Update count and insert
        insert_line = start_line + 1
        for i in range(start_line, end_line):
            if 'Discovered VLANs:' in lines[i]:
                current_count = int(re.search(r'\d+', lines[i]).group())
                lines[i] = f"**Discovered VLANs**: {current_count + 1}"
                insert_line = i + 1
                break
        
        lines.insert(insert_line, vlan_entry)
        
        frontmatter = self._update_frontmatter(frontmatter)
        changelog_entry = f"- **{datetime.now().strftime('%Y-%m-%d')}**: Added VLAN {vlan_id} - {vlan_info.get('name', 'N/A')}"
        lines = self._add_to_changelog(lines, changelog_entry)
        
        new_body = '\n'.join(lines)
        new_content = f"---\n{yaml.dump(frontmatter, default_flow_style=False)}---{new_body}"
        
        with open(self.skill_file, 'w') as f:
            f.write(new_content)
        
        logger.info(f"Added VLAN {vlan_id}")
        return True
    
    def add_monitoring_tool(self, tool_info: Dict) -> bool:
        """
        Add monitoring tool to the Monitoring & Management Tools section
        
        Args:
            tool_info: Dict with keys: tool_name, url, server_ip, purpose
        """
        if not self.skill_file.exists():
            return False
        
        self._create_backup()
        
        with open(self.skill_file, 'r') as f:
            content = f.read()
        
        tool_name = tool_info.get('tool_name', '')
        if self._check_duplicate(content, tool_name):
            logger.info(f"Tool {tool_name} already exists")
            return False
        
        frontmatter, body = self._parse_frontmatter(content)
        section_pos = self._find_section(body, 'Network Management Systems')
        
        if not section_pos:
            return False
        
        start_line, end_line = section_pos
        lines = body.split('\n')
        
        tool_entry = f"""
- **Tool**: {tool_info.get('tool_name', 'Unknown')}
- **URL**: `{tool_info.get('url', 'N/A')}`
- **Server IP**: `{tool_info.get('server_ip', 'N/A')}`
- **Purpose**: {tool_info.get('purpose', 'Network monitoring')}
- **Discovered**: {datetime.now().strftime("%Y-%m-%d")}
"""
        
        insert_line = start_line + 1
        for i in range(start_line, end_line):
            if 'Discovered Tools:' in lines[i]:
                current_count = int(re.search(r'\d+', lines[i]).group())
                lines[i] = f"**Discovered Tools**: {current_count + 1}"
                insert_line = i + 1
                break
        
        lines.insert(insert_line, tool_entry)
        
        frontmatter = self._update_frontmatter(frontmatter)
        changelog_entry = f"- **{datetime.now().strftime('%Y-%m-%d')}**: Added monitoring tool `{tool_name}`"
        lines = self._add_to_changelog(lines, changelog_entry)
        
        new_body = '\n'.join(lines)
        new_content = f"---\n{yaml.dump(frontmatter, default_flow_style=False)}---{new_body}"
        
        with open(self.skill_file, 'w') as f:
            f.write(new_content)
        
        logger.info(f"Added monitoring tool {tool_name}")
        return True
    
    def _add_to_changelog(self, lines: List[str], entry: str) -> List[str]:
        """Add entry to the Recent Changes section"""
        for i, line in enumerate(lines):
            if '### Recent Changes' in line:
                # Find the insertion point (after the comment)
                insert_pos = i + 2
                while insert_pos < len(lines) and lines[insert_pos].startswith('<!--'):
                    insert_pos += 1
                
                lines.insert(insert_pos, entry)
                break
        
        return lines
    
    def rollback(self) -> bool:
        """Rollback to the most recent backup"""
        if not self.backup_dir.exists():
            logger.error("No backup directory found")
            return False
        
        backups = sorted(self.backup_dir.glob("SKILL_*.md"), reverse=True)
        
        if not backups:
            logger.error("No backups available")
            return False
        
        latest_backup = backups[0]
        shutil.copy2(latest_backup, self.skill_file)
        logger.info(f"Rolled back to {latest_backup}")
        
        return True
    
    def get_changelog(self, max_entries: int = 10) -> List[str]:
        """Get recent changelog entries"""
        if not self.skill_file.exists():
            return []
        
        with open(self.skill_file, 'r') as f:
            content = f.read()
        
        _, body = self._parse_frontmatter(content)
        lines = body.split('\n')
        
        changelog = []
        in_changelog = False
        
        for line in lines:
            if '### Recent Changes' in line:
                in_changelog = True
                continue
            
            if in_changelog:
                if line.startswith('##'):  # Next section
                    break
                if line.startswith('- **'):
                    changelog.append(line)
                    if len(changelog) >= max_entries:
                        break
        
        return changelog
