---
name: drawio-network-diagram
description: "Generate network topology diagrams in draw.io (diagrams.net) format from structured data. Use when Claude needs to: (1) Create network diagrams from JSON topology data containing devices and links, (2) Visualize network architecture with routers, switches, firewalls, servers and connections, (3) Generate .drawio XML files showing network topology with device icons and interface labels, (4) Convert text descriptions of network layouts into visual diagrams"
---

# Draw.io Network Diagram Generation

## 🎯 INSTRUCTION TO LLM: READ THIS FIRST

**This skill contains ALL the information needed to generate draw.io network diagrams.**

When using this skill:
1. ✅ **READ this entire skill file** - all the code, examples, and patterns are here
2. ✅ **Use the code examples directly** - copy and adapt the Python/XML examples provided
3. ✅ **Follow the spacing/positioning values** - they are tested and proven
4. ✅ **once the diagram is generated, use the analyze_drawio_diagram tool to verify the diagram and get feedback**
5. ❌ **DO NOT search the web** for draw.io documentation - it will mislead you
6. ❌ **DO NOT use tool_use to find examples** - everything you need is in this file
7. ❌ **DO NOT reference external tutorials** - they use outdated or wrong approaches
8. ❌ **DO NOT try to "look up" draw.io syntax** - the correct syntax is documented here


**Why this matters:** Online draw.io tutorials use `image=img/lib/...` references which DON'T WORK. This skill shows the correct `shape=mxgraph.cisco19.rect` approach. Trust this skill, not the web.

**Your task:** Read the sections below, adapt the code examples to your specific topology, and generate the diagram. Everything you need is already here.

---

## ⚠️ CRITICAL: Common Mistakes to Avoid

**NEVER do these things (they break diagrams):**

1. ❌ **NEVER use `image=img/lib/cisco/...` for device icons**
   - External image references won't display
   - ALWAYS use: `shape=mxgraph.cisco19.rect;prIcon=router`
   - NOTE: `cisco19` is just the library name - it works for ALL vendors (Juniper, HP, Arista, etc.)

2. ❌ **NEVER try to find vendor-specific shape libraries**
   - There are no separate Juniper, HP, or Arista icon libraries in draw.io
   - Use `cisco19` library for all network devices regardless of vendor
   - Show vendor in device label: "Router-1\n(Juniper)" not in the icon style

3. ❌ **NEVER put labels in edge `value` attribute**
   - Example of WRONG: `<mxCell id="link1" value="Gi0/0 10.1.1.1" edge="1">`
   - ALWAYS create separate label cells as children of the edge

4. ❌ **NEVER use single centered labels on connections**
   - Must have source label AND target label as separate cells
   - Source: positioned at `-0.7`, Target: positioned at `0.7`

5. ❌ **NEVER put IP addresses in device labels**
   - Device labels show: hostname/device name and vendor
   - IP addresses go on connection labels (interface-specific)

6. ❌ **NEVER add extra links not in requirements**
   - Stick to the exact topology requested
   - Don't add "helpful" extras like legends unless asked

---

## Quick Reference

| Task | Approach |
|------|----------|
| From JSON topology data | Use Approach 1 (drawio_network_plot) or Approach 2 (direct XML) |
| Detect device types | Use device type detection heuristics |
| Apply proper icons | Use Cisco 19 shape library styles |
| Add interface labels | Create label cells parented to edge cells |

---

## Draw.io File Format Basics

Draw.io uses XML-based **mxGraphModel** format. Files have `.drawio` or `.xml` extensions.

### Minimal Structure

```xml
<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="app.diagrams.net">
  <diagram id="diagram_1" name="Page-1">
    <mxGraphModel dx="946" dy="469" grid="1" gridSize="10" pageWidth="1100" pageHeight="850">
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
        <!-- Devices and connections here -->
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

**Critical**: Root cells with id="0" and id="1" are mandatory.

---

## Device Nodes (Vertices)

```xml
<mxCell id="Router_1" 
        value="Edge-Router-01" 
        style="shape=mxgraph.cisco19.rect;prIcon=router;fillColor=#FAFAFA;strokeColor=#005073;verticalLabelPosition=bottom;verticalAlign=top"
        vertex="1" 
        parent="1">
  <mxGeometry x="100" y="100" width="50" height="50" as="geometry"/>
</mxCell>
```

**Key attributes:**
- `id`: Unique (use sanitized device_name)
- `value`: Display label
- `vertex="1"`: Marks as node
- `style`: Device icon and appearance

---

## Network Connections (Edges)

```xml
<mxCell id="link_0" 
        style="edgeStyle=orthogonalEdgeStyle;rounded=0;strokeWidth=2"
        edge="1" 
        parent="1" 
        source="Router_1" 
        target="Switch_1">
  <mxGeometry relative="1" as="geometry"/>
</mxCell>
```

**Key attributes:**
- `edge="1"`: Marks as connection
- `source` and `target`: Must match device IDs exactly

---

## Interface Labels

**CRITICAL: Labels MUST be separate child cells, NOT in edge value attribute.**

❌ **WRONG - Don't put labels in edge value:**
```xml
<mxCell id="link_0" 
        value="Gi0/0/1 192.168.10.1/24"  <!-- WRONG! -->
        edge="1" ...>
</mxCell>
```

❌ **WRONG - Don't use single centered label:**
```xml
<!-- This creates one label in the middle - can't show both interfaces -->
<mxCell id="label" value="Link Info" parent="link_0">
  <mxGeometry x="0" y="0" relative="1" as="geometry"/>  <!-- x="0" centers it -->
</mxCell>
```

✅ **CORRECT - Create TWO separate label cells:**

Labels for interface names and IPs are cells parented to the edge:

```xml
<!-- Source-side label (70% from source toward target) -->
<mxCell id="link_0_src" 
        value="Gi0/0/1&#xa;192.168.10.1/24" 
        style="text;html=1;align=center;labelBackgroundColor=#ffffff;fontSize=10"
        vertex="1" 
        connectable="0" 
        parent="link_0">
  <mxGeometry x="-0.7" relative="1" as="geometry">
    <mxPoint x="0" y="-15" as="offset"/>
  </mxGeometry>
</mxCell>

<!-- Target-side label (70% from target toward source) -->
<mxCell id="link_0_tgt" 
        value="Gi0/0/2&#xa;192.168.10.2/24" 
        style="text;html=1;align=center;labelBackgroundColor=#ffffff;fontSize=10"
        vertex="1" 
        connectable="0" 
        parent="link_0">
  <mxGeometry x="0.7" relative="1" as="geometry">
    <mxPoint x="0" y="-15" as="offset"/>
  </mxGeometry>
</mxCell>
```

**Key points:**
- `parent="link_0"`: Label is child of the edge
- `x="-0.7"`: 70% from source end (negative = from source)
- `x="0.7"`: 70% from target end (positive = from target)
- `y="-15"`: Offset above the line for readability
- Use `&#xa;` for line breaks in XML
- **NEVER use `x="-1"` or `x="1"`** - puts labels at device edges causing overlaps

---

## Device Icon Styles (Cisco 19 Library)

**CRITICAL: Use shape library styles, NOT image references.**

❌ **WRONG - Don't use image paths:**
```xml
style="image;html=1;image=img/lib/cisco/routers/router.svg;..."
```

✅ **CORRECT - Use shape library:**
```xml
style="shape=mxgraph.cisco19.rect;prIcon=router;fillColor=#FAFAFA;strokeColor=#005073;..."
```

**NOTE:** The `mxgraph.cisco19` library name is misleading - it's a generic network icon library that works for ALL vendors (Cisco, Juniper, HP, Arista, etc.). The icons are vendor-neutral shapes (router, switch, server). Don't try to find "Juniper-specific" or "HP-specific" shape libraries - they don't exist. Use cisco19 for all network devices regardless of vendor.

**Standard device type styles (vendor-agnostic):**

```python
DEVICE_STYLES = {
    'router': 'shape=mxgraph.cisco19.rect;prIcon=router;fillColor=#FAFAFA;strokeColor=#005073;verticalLabelPosition=bottom;verticalAlign=top',
    'l3_switch': 'shape=mxgraph.cisco19.rect;prIcon=l3_switch;fillColor=#FAFAFA;strokeColor=#005073;verticalLabelPosition=bottom;verticalAlign=top',
    'l2_switch': 'shape=mxgraph.cisco19.rect;prIcon=l2_switch;fillColor=#FAFAFA;strokeColor=#005073;verticalLabelPosition=bottom;verticalAlign=top',
    'firewall': 'shape=mxgraph.cisco19.rect;prIcon=firewall;fillColor=#FAFAFA;strokeColor=#005073;verticalLabelPosition=bottom;verticalAlign=top',
    'server': 'shape=mxgraph.cisco19.rect;prIcon=server;fillColor=#FAFAFA;strokeColor=#005073;verticalLabelPosition=bottom;verticalAlign=top',
    'pc': 'shape=mxgraph.cisco19.rect;prIcon=pc;fillColor=#FAFAFA;strokeColor=#005073;verticalLabelPosition=bottom;verticalAlign=top',
    'cloud': 'shape=mxgraph.cisco19.rect;prIcon=cloud;fillColor=#FAFAFA;strokeColor=#005073;verticalLabelPosition=bottom;verticalAlign=top'
}
```

**Vendor identification:** Show vendor in the device label, not in the icon style:
```python
# Device label shows vendor
label = f"{device['device_name']}\n({device['vendor']})"
# Example: "Core-Router-1\n(Juniper)" or "Dist-Switch-1\n(Cisco)"
```

Add `;aspect=fixed;align=center;pointerEvents=1;html=1` for consistency.

---

## Device Type Detection

Infer device type from name patterns:

```python
def detect_device_type(device_name):
    name = device_name.lower()
    
    if any(x in name for x in ['router', 'csr', 'asr']):
        return 'router'
    elif any(x in name for x in ['switch', 'nexus', 'catalyst']):
        if any(x in name for x in ['core', 'spine', 'l3', 'distribution']):
            return 'l3_switch'
        return 'l2_switch'
    elif any(x in name for x in ['firewall', 'fw', 'asa']):
        return 'firewall'
    elif any(x in name for x in ['server', 'srv']):
        return 'server'
    elif any(x in name for x in ['pc', 'workstation', 'laptop']):
        return 'pc'
    elif any(x in name for x in ['cloud', 'wan', 'internet']):
        return 'cloud'
    
    return 'server'  # Default
```

---

## Layout Strategy

**CRITICAL FOR VISUAL QUALITY**: Proper layout is the difference between a professional diagram and a mess.

### Key Layout Principles

1. **Center devices horizontally** - Calculate total width and center on canvas
2. **Use generous spacing** - Minimum 200px horizontal, 300px+ vertical between tiers
3. **Use straight lines** - Avoid orthogonal edge routing which causes overlapping
4. **Position labels on lines** - Use relative position 0.6-0.8, not at endpoints

### Recommended Spacing

```python
# Minimum spacing recommendations (in pixels)
SPACING = {
    'horizontal_between_devices': 200,  # Minimum, use 250-400 for cleaner look
    'vertical_between_tiers': 300,      # Minimum, use 350-500 for hierarchy
    'device_size': 70,                   # Icon width/height
    'page_width': 1400,                  # Standard canvas width
    'page_height': 850                   # Standard canvas height
}
```

### Proper Centering Logic

```python
def calculate_positions(devices, links):
    """Place devices in hierarchical tiers with proper centering"""
    tiers = {
        'core': {'y': 150, 'devices': []},
        'distribution': {'y': 500, 'devices': []},
        'access': {'y': 700, 'devices': []}
    }
    
    # Classify devices into tiers
    for device in devices:
        tier = classify_tier(device['device_name'])
        tiers[tier]['devices'].append(device)
    
    # Calculate centered positions for each tier
    positions = {}
    page_width = 1400
    
    for tier_name, tier_data in tiers.items():
        count = len(tier_data['devices'])
        if count == 0:
            continue
        
        # Generous spacing based on tier
        if tier_name == 'core':
            spacing = 400  # Wide spacing for core
        else:
            spacing = 220  # Good spacing for distribution/access
        
        # Calculate total width and center
        total_width = (count - 1) * spacing if count > 1 else 0
        start_x = (page_width - total_width) / 2
        
        for i, device in enumerate(tier_data['devices']):
            x = start_x + (i * spacing)
            y = tier_data['y']
            positions[device['device_name']] = {'x': x, 'y': y}
    
    return positions
```

### Edge Styling - Use Straight Lines

**DON'T use orthogonal routing** - it causes messy overlapping:
```python
# BAD - causes overlaps
style='edgeStyle=orthogonalEdgeStyle;rounded=0;...'
```

**DO use straight lines**:
```python
# GOOD - clean direct connections
style='rounded=0;html=1;strokeWidth=2;strokeColor=#000000;endArrow=none;endFill=0'
```

### Label Positioning

Position labels along the line, not at endpoints:

```python
# Source label - positioned 70% from source toward target
src_label_geom = {
    'x': '-0.7',  # 70% from source (negative = from source end)
    'relative': '1',
    'as': 'geometry'
}
# Offset slightly above the line
offset = {'x': '0', 'y': '-15', 'as': 'offset'}

# Target label - positioned 70% from target toward source  
tgt_label_geom = {
    'x': '0.7',  # 70% from target (positive = from target end)
    'relative': '1',
    'as': 'geometry'
}
```

**Avoid positioning at -1 or 1** (device endpoints) - causes label overlaps.

---

## Implementation Approach 1: drawio_network_plot Library

```bash
pip install drawio-network-plot --break-system-packages
```

```python
from drawio_network_plot import NetPlot

plot = NetPlot()

# Add devices
devices = [
    {'nodeName': 'Router_1', 'nodeType': 'router', 'hostname': 'edge-router-01'},
    {'nodeName': 'Switch_1', 'nodeType': 'l3_switch', 'hostname': 'core-switch-01'}
]
plot.addNodeList(devices)

# Add connections
links = [
    {'sourceNodeID': 'Router_1', 'destinationNodeID': 'Switch_1', 
     'source_label': 'Gi0/1', 'target_label': 'Eth1/1'}
]
plot.addLinkList(links)

# Export
plot.exportXML('network.drawio')
```

---

## Implementation Approach 2: Direct XML Generation

```python
import xml.etree.ElementTree as ET
from xml.dom import minidom

def create_diagram(devices, links, output_file):
    # Create structure
    mxfile = ET.Element('mxfile', host="app.diagrams.net")
    diagram = ET.SubElement(mxfile, 'diagram', id="topology", name="Network")
    model = ET.SubElement(diagram, 'mxGraphModel', {
        'dx': '1200', 'dy': '800', 'grid': '1', 'gridSize': '10',
        'pageWidth': '1400', 'pageHeight': '850'
    })
    root = ET.SubElement(model, 'root')
    
    # Root cells (required)
    ET.SubElement(root, 'mxCell', id='0')
    ET.SubElement(root, 'mxCell', id='1', parent='0')
    
    positions = calculate_positions(devices, links)
    
    # Add devices
    for device in devices:
        dev_id = sanitize_id(device['device_name'])
        dev_type = detect_device_type(device['device_name'])
        style = DEVICE_STYLES.get(dev_type, DEVICE_STYLES['server'])
        pos = positions.get(device['device_name'], {'x': 0, 'y': 0})
        
        cell = ET.SubElement(root, 'mxCell', {
            'id': dev_id,
            'value': device['device_name'],
            'style': style + ';aspect=fixed;align=center',
            'vertex': '1',
            'parent': '1'
        })
        ET.SubElement(cell, 'mxGeometry', {
            'x': str(pos['x']), 'y': str(pos['y']),
            'width': '50', 'height': '50', 'as': 'geometry'
        })
    
    # Add links
    for idx, link in enumerate(links):
        link_id = f"link_{idx}"
        src_id = sanitize_id(link['device1'])
        tgt_id = sanitize_id(link['device2'])
        
        edge = ET.SubElement(root, 'mxCell', {
            'id': link_id,
            'style': 'rounded=0;html=1;strokeWidth=2;strokeColor=#000000;endArrow=none;endFill=0',
            'edge': '1',
            'parent': '1',
            'source': src_id,
            'target': tgt_id
        })
        ET.SubElement(edge, 'mxGeometry', {'relative': '1', 'as': 'geometry'})
        
        # Add interface labels
        if 'interface1' in link:
            label = link['interface1']
            if 'link_ip' in link:
                label += f"&#xa;{link['link_ip']}"
            
            src_label = ET.SubElement(root, 'mxCell', {
                'id': f"{link_id}_src",
                'value': label,
                'style': 'text;html=1;align=center;labelBackgroundColor=#ffffff;fontSize=10',
                'vertex': '1',
                'connectable': '0',
                'parent': link_id
            })
            geom = ET.SubElement(src_label, 'mxGeometry', {
                'x': '-0.7', 'relative': '1', 'as': 'geometry'
            })
            ET.SubElement(geom, 'mxPoint', {'x': '0', 'y': '-15', 'as': 'offset'})
        
        if 'interface2' in link:
            tgt_label = ET.SubElement(root, 'mxCell', {
                'id': f"{link_id}_tgt",
                'value': link['interface2'],
                'style': 'text;html=1;align=center;labelBackgroundColor=#ffffff;fontSize=10',
                'vertex': '1',
                'connectable': '0',
                'parent': link_id
            })
            geom = ET.SubElement(tgt_label, 'mxGeometry', {
                'x': '0.7', 'relative': '1', 'as': 'geometry'
            })
            ET.SubElement(geom, 'mxPoint', {'x': '0', 'y': '-15', 'as': 'offset'})
    
    # Write file
    xml_str = minidom.parseString(ET.tostring(mxfile)).toprettyxml(indent="  ")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(xml_str)

def sanitize_id(name):
    """Convert to valid XML ID"""
    return name.replace(' ', '_').replace('-', '_').replace('.', '_')
```

**IMPORTANT REMINDER:** All the code you need is above. Do NOT search for additional examples online. Do NOT use tool_use to find "better" approaches. The patterns shown above are tested and correct. Simply adapt this code to your specific topology requirements.

---

## Handling JSON Input

Parse topology JSON and generate diagram:

```python
import json

with open('topology.json') as f:
    data = json.load(f)

# Transform to diagram format
devices = []
for dev in data['devices']:
    devices.append({
        'device_name': dev['device_name'],
        'ip': dev.get('management_ip_address'),
        'brand': dev.get('brand')
    })

links = []
for link in data['topology_links']:
    links.append({
        'device1': link['device1'],
        'interface1': link['interface1'],
        'device2': link['device2'],
        'interface2': link['interface2'],
        'link_ip': link.get('link_ip')
    })

create_diagram(devices, links, 'network_topology.drawio')
```

---

## Advanced: Protocol Annotations

Add routing protocol or VLAN info as text annotations:

```xml
<mxCell id="annotation_bgp" 
        value="BGP AS 65000" 
        style="text;html=1;fontSize=12;fontStyle=1;fillColor=none;strokeColor=none"
        vertex="1" parent="1">
  <mxGeometry x="500" y="50" width="120" height="30" as="geometry"/>
</mxCell>
```

Or use swimlane containers to group devices by zone:

```xml
<mxCell id="dmz_zone" 
        value="DMZ Zone" 
        style="swimlane;fillColor=#dae8fc;strokeColor=#6c8ebf" 
        vertex="1" parent="1">
  <mxGeometry x="50" y="50" width="400" height="300" as="geometry"/>
</mxCell>
```

---

## 📋 Workflow: How to Use This Skill

**Step-by-step process (follow this, don't improvise):**

1. **Parse the input** - Extract devices and links from JSON/text
2. **Classify device types** - Use the `detect_device_type()` function from this skill
3. **Calculate positions** - Use the `calculate_positions()` function with centering logic from this skill
4. **Generate XML** - Use the `create_diagram()` template from this skill
5. **Validate output** - Check against the validation checklist below
6. **Write file** - Save to `/mnt/user-data/outputs/` directory

**Do NOT:**
- ❌ Search for "how to create draw.io diagrams" online
- ❌ Look for Python libraries besides the ones mentioned here
- ❌ Try to "improve" the code patterns shown in this skill
- ❌ Add features not requested (legends, extra links, etc.)
- ❌ Use different XML structure than shown in examples

**Remember:** This skill is the result of extensive testing and iteration. The code patterns here WORK. Trust them.

---

## Visual Quality Checklist

Before finalizing diagram, ensure it meets these visual standards:

**Layout Quality:**
- ✓ Devices are centered on canvas (not bunched to one side)
- ✓ Horizontal spacing between devices: 200px minimum, 250-400px preferred
- ✓ Vertical spacing between tiers: 300px minimum, 350-500px preferred
- ✓ Device icons are appropriately sized (60-80px)

**Connection Quality:**
- ✓ Links use straight lines (no orthogonal routing causing overlaps)
- ✓ Interface labels positioned along lines (not at device endpoints)
- ✓ Labels have white backgrounds for readability
- ✓ No label overlaps or collisions

**Professional Appearance:**
- ✓ Hierarchical structure is clear (core top, distribution middle, access bottom)
- ✓ Symmetry where appropriate (equal spacing for similar devices)
- ✓ Protocol annotations clearly visible
- ✓ Diagram fits on one screen without scrolling

**Common Visual Mistakes to Avoid:**
- ❌ All devices stacked on left side (forgot to center)
- ❌ Overlapping connection lines (used orthogonal routing)
- ❌ Labels on device edges causing overlaps (used x="-1" or x="1")
- ❌ Insufficient spacing making diagram cramped (<200px horizontal)
- ❌ No vertical hierarchy (all devices at same Y coordinate)

---

## Validation Checklist

Before considering diagram complete:

1. XML is well-formed (valid syntax)
2. Root cells (id="0" and id="1") present
3. All device IDs are unique
4. All edge source/target IDs reference existing devices
5. Geometry values are positive numbers
6. File opens in draw.io without errors

---

## Post-Generation Steps

After generating .drawio file:

1. Open in draw.io (app.diagrams.net)
2. Apply layout: **Arrange > Layout > Vertical Tree** (or Horizontal/Organic)
3. Verify all devices visible and properly connected
4. Adjust spacing and alignment as needed
5. Export to PNG/SVG/PDF for documentation

---

## 🎓 Final Reminder for LLM

**You have successfully completed this task when:**
- ✅ You generated a `.drawio` XML file using the patterns from this skill
- ✅ You used `shape=mxgraph.cisco19.rect;prIcon=...` for ALL device icons (works for any vendor)
- ✅ You showed vendor names in device labels (e.g., "Router-1\n(Juniper)")
- ✅ You created separate source and target labels for each connection
- ✅ You calculated centered positions for devices
- ✅ You used straight lines (not orthogonal routing)
- ✅ You saved the file to `/mnt/user-data/outputs/`

**You have FAILED this task if:**
- ❌ You searched the web for draw.io documentation
- ❌ You tried to find "vendor-specific" shape libraries (they don't exist - use cisco19 for all)
- ❌ You used `image=img/lib/...` references
- ❌ You put labels in edge `value` attributes
- ❌ You used `x="-1"` or `x="1"` for label positioning
- ❌ You added features not requested (legends, extra links, etc.)
- ❌ You forgot to center devices horizontally

**This skill is complete and tested.** Everything you need is documented above. Read it carefully, follow the examples, and generate the diagram. Do not overthink it or try to find "better" ways.
