"""
Skill Update Detector - Intelligently detects when skill updates are needed

This module provides:
- Context analysis to identify network-related information
- LLM-based information extraction
- Confidence scoring for update proposals
- Multi-skill support
"""

import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class SkillUpdateDetector:
    """Detects when skill updates are needed based on conversation context"""
    
    def __init__(self, skills_dir: str = "skills"):
        """
        Initialize the update detector
        
        Args:
            skills_dir: Path to the skills directory
        """
        self.skills_dir = Path(skills_dir)
        self.skills = self._discover_skills()
    
    def _discover_skills(self) -> Dict[str, Dict]:
        """
        Discover all available skills and load their configurations
        
        Returns:
            Dict mapping skill_name -> config
        """
        skills = {}
        
        if not self.skills_dir.exists():
            logger.warning(f"Skills directory not found: {self.skills_dir}")
            return skills
        logger.info(f"Skills directory: {self.skills_dir}")
        for skill_path in self.skills_dir.iterdir():
            if not skill_path.is_dir():
                continue
            
            config_file = skill_path / "skill_config.yaml"
            if not config_file.exists():
                continue
            
            try:
                with open(config_file, 'r') as f:
                    config = yaml.safe_load(f) or {}
                
                skill_name = config.get('skill', {}).get('name', skill_path.name)
                skills[skill_name] = {
                    'path': skill_path,
                    'config': config
                }
                logger.info(f"Discovered skill: {skill_name}")
            except Exception as e:
                logger.error(f"Failed to load skill config from {config_file}: {e}")
        
        return skills
    
    def match_skills_to_context(self, context: str) -> List[str]:
        """
        Determine which skills are relevant to the given context
        
        Args:
            context: Conversation context (tool outputs, agent responses, etc.)
        
        Returns:
            List of relevant skill names
        """
        relevant_skills = []
        context_lower = context.lower()
        
        for skill_name, skill_data in self.skills.items():
            config = skill_data['config']
            
            # Check if skill has auto_update enabled
            if not config.get('skill', {}).get('auto_update_enabled', True):
                continue
            
            # Get extraction patterns
            patterns = config.get('extraction_patterns', {})
            
            # Check if any keywords match
            for category, pattern_data in patterns.items():
                keywords = pattern_data.get('keywords', [])
                
                for keyword in keywords:
                    if keyword.lower() in context_lower:
                        relevant_skills.append(skill_name)
                        logger.info(f"Matched skill '{skill_name}' via keyword '{keyword}'")
                        break
                
                if skill_name in relevant_skills:
                    break
        
        return list(set(relevant_skills))  # Remove duplicates
    
    def extract_network_device(self, context: str) -> Optional[Dict]:
        """
        Extract network device information from context
        
        Args:
            context: Text containing potential device information
        
        Returns:
            Dict with device info or None
        """
        device_info = {}
        
        # Extract IP address
        ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
        ip_match = re.search(ip_pattern, context)
        if ip_match:
            device_info['ip_address'] = ip_match.group()
        
        # Extract hostname (common patterns)
        hostname_patterns = [
            r'(?:hostname|host|device):\s*([a-zA-Z0-9\-\.]+)',
            r'([a-zA-Z0-9\-]+(?:rtr|sw|fw|lb|router|switch|firewall)[a-zA-Z0-9\-]*)',
            r'([a-zA-Z0-9\-]+\.(?:corp|local|internal)[a-zA-Z0-9\-\.]*)',
        ]
        
        for pattern in hostname_patterns:
            match = re.search(pattern, context, re.IGNORECASE)
            if match:
                device_info['hostname'] = match.group(1)
                break
        
        # Determine device type
        device_type_keywords = {
            'router': ['router', 'rtr', 'core-rtr', 'edge-rtr'],
            'switch': ['switch', 'sw', 'dist-sw', 'access-sw'],
            'firewall': ['firewall', 'fw', 'edge-fw', 'palo alto', 'fortinet'],
            'load_balancer': ['load balancer', 'lb', 'f5', 'big-ip'],
        }
        
        context_lower = context.lower()
        for device_type, keywords in device_type_keywords.items():
            if any(kw in context_lower for kw in keywords):
                device_info['device_type'] = device_type
                break
        
        # Extract model/vendor
        vendor_patterns = [
            r'(Cisco\s+\w+\s+\d+)',
            r'(Palo Alto\s+PA-\d+)',
            r'(Fortinet\s+FortiGate\s+\w+)',
            r'(F5\s+BIG-IP)',
            r'(Juniper\s+\w+)',
        ]
        
        for pattern in vendor_patterns:
            match = re.search(pattern, context, re.IGNORECASE)
            if match:
                device_info['model'] = match.group(1)
                break
        
        # Only return if we have at least hostname or IP
        if 'hostname' in device_info or 'ip_address' in device_info:
            return device_info
        
        return None
    
    def extract_vlan(self, context: str) -> Optional[Dict]:
        """
        Extract VLAN information from context
        
        Args:
            context: Text containing potential VLAN information
        
        Returns:
            Dict with VLAN info or None
        """
        vlan_info = {}
        
        # Extract VLAN ID
        vlan_id_pattern = r'VLAN\s+(\d+)'
        vlan_match = re.search(vlan_id_pattern, context, re.IGNORECASE)
        if vlan_match:
            vlan_info['vlan_id'] = vlan_match.group(1)
        
        # Extract subnet
        subnet_pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2})'
        subnet_match = re.search(subnet_pattern, context)
        if subnet_match:
            vlan_info['subnet'] = subnet_match.group(1)
        
        # Extract name/purpose (heuristic)
        if 'vlan_id' in vlan_info:
            # Look for text near VLAN ID
            context_around = context[max(0, vlan_match.start()-50):min(len(context), vlan_match.end()+100)]
            
            # Common VLAN names
            name_patterns = [
                r'VLAN\s+\d+:\s*([A-Za-z\s]+)',
                r'name:\s*([A-Za-z\s]+)',
            ]
            
            for pattern in name_patterns:
                match = re.search(pattern, context_around, re.IGNORECASE)
                if match:
                    vlan_info['name'] = match.group(1).strip()
                    break
        
        if 'vlan_id' in vlan_info:
            return vlan_info
        
        return None
    
    def extract_monitoring_tool(self, context: str) -> Optional[Dict]:
        """
        Extract monitoring tool information from context
        
        Args:
            context: Text containing potential monitoring tool info
        
        Returns:
            Dict with tool info or None
        """
        tool_info = {}
        
        # Extract URL
        url_pattern = r'https?://[a-zA-Z0-9\-\.]+(?:\.[a-zA-Z]{2,})?(?:/[^\s]*)?'
        url_match = re.search(url_pattern, context)
        if url_match:
            tool_info['url'] = url_match.group()
        
        # Extract tool name
        tool_keywords = {
            'SolarWinds': ['solarwinds', 'npm'],
            'Splunk': ['splunk'],
            'NetFlow': ['netflow', 'scrutinizer', 'plixer'],
            'Cisco Prime': ['prime', 'cisco prime'],
            'PRTG': ['prtg'],
            'Nagios': ['nagios'],
            'Zabbix': ['zabbix'],
            'Prometheus': ['prometheus'],
            'Grafana': ['grafana'],
        }
        
        context_lower = context.lower()
        for tool_name, keywords in tool_keywords.items():
            if any(kw in context_lower for kw in keywords):
                tool_info['tool_name'] = tool_name
                break
        
        # Extract server IP
        if 'url' not in tool_info:
            ip_pattern = r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b'
            ip_match = re.search(ip_pattern, context)
            if ip_match:
                tool_info['server_ip'] = ip_match.group(1)
        
        if 'tool_name' in tool_info or 'url' in tool_info:
            return tool_info
        
        return None
    
    def calculate_confidence(self, extracted_info: Dict, info_type: str) -> int:
        """
        Calculate confidence score for extracted information
        
        Args:
            extracted_info: The extracted information dict
            info_type: Type of information (network_device, vlan, monitoring_tool, etc.)
        
        Returns:
            Confidence score (0-100)
        """
        if not extracted_info:
            return 0
        
        confidence = 0
        
        if info_type == 'network_device':
            # Higher confidence if we have more fields
            if 'hostname' in extracted_info:
                confidence += 40
            if 'ip_address' in extracted_info:
                confidence += 30
            if 'model' in extracted_info:
                confidence += 20
            if 'device_type' in extracted_info:
                confidence += 10
        
        elif info_type == 'vlan':
            if 'vlan_id' in extracted_info:
                confidence += 50
            if 'subnet' in extracted_info:
                confidence += 30
            if 'name' in extracted_info:
                confidence += 20
        
        elif info_type == 'monitoring_tool':
            if 'tool_name' in extracted_info:
                confidence += 50
            if 'url' in extracted_info:
                confidence += 40
            if 'server_ip' in extracted_info:
                confidence += 10
        
        return min(confidence, 100)
    
    def should_update(self, context: str, skill_name: str) -> Tuple[bool, List[Dict]]:
        """
        Determine if a skill should be updated based on context
        
        Args:
            context: Conversation context
            skill_name: Name of the skill to check
        
        Returns:
            (should_update, list_of_update_proposals)
        """
        if skill_name not in self.skills:
            return False, []
        
        config = self.skills[skill_name]['config']
        threshold = config.get('update_triggers', {}).get('confidence_threshold', 75)
        
        proposals = []
        
        # Try to extract different types of information
        device_info = self.extract_network_device(context)
        if device_info:
            confidence = self.calculate_confidence(device_info, 'network_device')
            if confidence >= threshold:
                proposals.append({
                    'type': 'network_device',
                    'data': device_info,
                    'confidence': confidence,
                    'reason': f"Discovered network device: {device_info.get('hostname', device_info.get('ip_address', 'Unknown'))}"
                })
        
        vlan_info = self.extract_vlan(context)
        if vlan_info:
            confidence = self.calculate_confidence(vlan_info, 'vlan')
            if confidence >= threshold:
                proposals.append({
                    'type': 'vlan',
                    'data': vlan_info,
                    'confidence': confidence,
                    'reason': f"Discovered VLAN {vlan_info.get('vlan_id', 'Unknown')}"
                })
        
        tool_info = self.extract_monitoring_tool(context)
        if tool_info:
            confidence = self.calculate_confidence(tool_info, 'monitoring_tool')
            if confidence >= threshold:
                proposals.append({
                    'type': 'monitoring_tool',
                    'data': tool_info,
                    'confidence': confidence,
                    'reason': f"Discovered monitoring tool: {tool_info.get('tool_name', tool_info.get('url', 'Unknown'))}"
                })
        
        should_update = len(proposals) > 0
        return should_update, proposals
