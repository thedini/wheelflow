# User Story: US-003 - Force Distribution Graph

## Title
Display Cumulative Force Distribution Along Wheel Position

## Priority
**HIGH** - Core visualization feature

## User Story
As a **wheel aerodynamicist**, I want to **see a graph showing how drag force accumulates along the wheel** so that I can **identify which sections of the wheel contribute most to total drag**.

---

## Acceptance Criteria

### AC1: Graph Display
- [ ] Show cumulative drag force (N) on Y-axis
- [ ] Show position along model (m) on X-axis
- [ ] Plot smooth curve showing force accumulation
- [ ] Support logarithmic Y-axis scale for large ranges

### AC2: Force Component Selection
- [ ] Dropdown to select force type:
  - Cumulative Drag
  - Drag X / Drag Y / Drag Z components
  - Cumulative Lift
  - Lift X / Lift Y / Lift Z components
  - Cumulative Side
  - Side X / Side Y / Side Z components

### AC3: Model Overlay Toggle
- [ ] Checkbox to show/hide wheel outline on graph
- [ ] Overlay should indicate where wheel rim/spokes/hub are positioned
- [ ] Help users correlate force spikes with geometry features

### AC4: Interactive Features
- [ ] Hover to show exact values at any point
- [ ] Zoom and pan capabilities
- [ ] Reset view button

---

## Technical Notes

### Data Source
From OpenFOAM postProcessing:
```
forces/0/forces.dat
- Contains cumulative force data
- Extract per-cell contributions
- Sum along model axis (typically X or Z)
```

### Reference Implementation
AeroCloud shows this as "Force distribution" card with:
- Teal/cyan area fill under curve
- Position range from -0.65m to -0.05m (example)
- Force range 0.0e+0 to 9.0e-1 N
- "Model" checkbox toggle

### Calculation
```python
# Pseudo-code for cumulative force
positions = sorted(cell_centers_along_axis)
cumulative = []
running_sum = 0
for pos in positions:
    running_sum += force_at_position[pos]
    cumulative.append((pos, running_sum))
```

---

## UI Mockup Specification

```
┌─────────────────────────────────────────────────────────────┐
│ Force distribution          [Cumulative Drag ▼]  □ Model   │
├─────────────────────────────────────────────────────────────┤
│                                                    0.9      │
│                                              ████           │
│ Cumulative                              █████  █            │
│ Drag Force                          ████      ██            │
│ [N]                             ████           ██           │
│                              ███                ██          │
│                          ███                     █          │
│                     █████                         █         │
│               ██████                               █        │
│          █████                                      █       │
│     █████                                            0.0    │
├─────────────────────────────────────────────────────────────┤
│ -0.65  -0.55  -0.45  -0.35  -0.25  -0.15  -0.05           │
│              Position along model [m]                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Definition of Done
- [ ] Graph renders correctly with force data
- [ ] All force components selectable
- [ ] Model overlay works
- [ ] Interactive hover shows values
- [ ] Responsive layout
- [ ] Unit tests pass

---

## Estimated Effort
**Story Points**: 5

## Dependencies
- Results dashboard (US-001)
- Force data extraction from OpenFOAM output

## Related Research
From academic studies, the cumulative drag plot helps identify:
- Spoke contribution regions (periodic spikes)
- Rim depth impact (gradual buildup)
- Hub interference effects

