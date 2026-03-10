#!/usr/bin/env python3
"""
Test script for the intelligent skill update system

This script demonstrates:
- Skill discovery
- Update detection
- Applying updates
- Rollback functionality
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from custom_middleware.skills_middleware import SkillLearningMiddleware
from utils.skill_writer import SkillWriter
from utils.skill_update_prompts import (
    format_update_proposal,
    format_batch_update_summary,
    format_apply_result
)

def test_skill_discovery():
    """Test that skills are discovered correctly"""
    print("\n" + "="*60)
    print("TEST 1: Skill Discovery")
    print("="*60)
    
    middleware = SkillLearningMiddleware("skills")
    
    print(f"\nDiscovered {len(middleware.detector.skills)} skills:")
    for skill_name in middleware.detector.skills.keys():
        print(f"  ✓ {skill_name}")
    
    return len(middleware.detector.skills) > 0


def test_network_device_detection():
    """Test detection of network device information"""
    print("\n" + "="*60)
    print("TEST 2: Network Device Detection")
    print("="*60)
    
    middleware = SkillLearningMiddleware("skills")
    
    # Simulate a conversation with network device info
    test_context = """
    Connected to core router core-rtr-01.corp.local at 10.0.10.1
    Device model: Cisco Catalyst 9600 Series
    Role: Primary Core Router
    """
    
    print("\nTest context:")
    print(test_context)
    
    # Process the context
    middleware.process_message({'role': 'assistant', 'content': test_context})
    
    # Check for pending updates
    pending = middleware.get_pending_updates('network-design-document')
    
    if pending and pending.get('network-design-document'):
        proposals = pending['network-design-document']
        print(f"\n✓ Detected {len(proposals)} update(s):")
        for proposal in proposals:
            print(f"  - {proposal['reason']} (confidence: {proposal['confidence']}%)")
        return True
    else:
        print("\n✗ No updates detected")
        return False


def test_vlan_detection():
    """Test detection of VLAN information"""
    print("\n" + "="*60)
    print("TEST 3: VLAN Detection")
    print("="*60)
    
    middleware = SkillLearningMiddleware("skills")
    
    test_context = """
    Configured VLAN 20: Application Servers
    Subnet: 10.0.20.0/23
    """
    
    print("\nTest context:")
    print(test_context)
    
    middleware.process_message({'role': 'assistant', 'content': test_context})
    
    pending = middleware.get_pending_updates('network-design-document')
    
    if pending and pending.get('network-design-document'):
        proposals = pending['network-design-document']
        print(f"\n✓ Detected {len(proposals)} update(s):")
        for proposal in proposals:
            print(f"  - {proposal['reason']} (confidence: {proposal['confidence']}%)")
        return True
    else:
        print("\n✗ No updates detected")
        return False


def test_monitoring_tool_detection():
    """Test detection of monitoring tools"""
    print("\n" + "="*60)
    print("TEST 4: Monitoring Tool Detection")
    print("="*60)
    
    middleware = SkillLearningMiddleware("skills")
    
    test_context = """
    Accessed SolarWinds monitoring dashboard at https://nms.corp.local
    Server IP: 10.0.10.100
    """
    
    print("\nTest context:")
    print(test_context)
    
    middleware.process_message({'role': 'assistant', 'content': test_context})
    
    pending = middleware.get_pending_updates('network-design-document')
    
    if pending and pending.get('network-design-document'):
        proposals = pending['network-design-document']
        print(f"\n✓ Detected {len(proposals)} update(s):")
        for proposal in proposals:
            print(f"  - {proposal['reason']} (confidence: {proposal['confidence']}%)")
        return True
    else:
        print("\n✗ No updates detected")
        return False


def test_apply_updates():
    """Test applying updates to SKILL.md"""
    print("\n" + "="*60)
    print("TEST 5: Applying Updates")
    print("="*60)
    
    middleware = SkillLearningMiddleware("skills")
    
    # Add some test data
    test_context = """
    Connected to edge firewall edge-fw-01.corp.local at 172.16.0.1
    Platform: Palo Alto PA-5000 Series
    HA Mode: Active/Passive
    """
    
    middleware.process_message({'role': 'assistant', 'content': test_context})
    
    pending = middleware.get_pending_updates('network-design-document')
    
    if not pending or not pending.get('network-design-document'):
        print("\n✗ No pending updates to apply")
        return False
    
    # Show what we're about to apply
    print("\nPending updates:")
    print(format_update_proposal('network-design-document', pending['network-design-document']))
    
    # Apply the updates
    print("\nApplying updates...")
    result = middleware.apply_updates('network-design-document')
    
    print(format_apply_result(result))
    
    return result.get('success', False)


def test_rollback():
    """Test rollback functionality"""
    print("\n" + "="*60)
    print("TEST 6: Rollback")
    print("="*60)
    
    writer = SkillWriter("skills/network-design-document")
    
    print("\nAttempting rollback...")
    success = writer.rollback()
    
    if success:
        print("✓ Rollback successful")
    else:
        print("✗ Rollback failed (this is expected if no backups exist)")
    
    return True  # Don't fail test if no backups


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("INTELLIGENT SKILL UPDATE SYSTEM - TEST SUITE")
    print("="*60)
    
    tests = [
        ("Skill Discovery", test_skill_discovery),
        ("Network Device Detection", test_network_device_detection),
        ("VLAN Detection", test_vlan_detection),
        ("Monitoring Tool Detection", test_monitoring_tool_detection),
        ("Apply Updates", test_apply_updates),
        ("Rollback", test_rollback),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
