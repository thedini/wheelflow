# User Story: US-004 - Pressure Slice Visualization

## Title
View Pressure Coefficient Slices Through Flow Field

## Priority
**HIGH** - Essential CFD visualization

## User Story
As a **CFD engineer**, I want to **view 2D slices of the pressure field around my wheel** so that I can **understand the flow patterns, identify separation regions, and validate simulation quality**.

---

## Acceptance Criteria

### AC1: Slice Display
- [ ] Show 2D color contour plot of selected field
- [ ] Display slice position indicator
- [ ] Show wheel cross-section outline on slice
- [ ] Include color scale/legend with range

### AC2: Slice Navigation
- [ ] Slider to move through slices (e.g., 49 slices)
- [ ] Previous/Next buttons
- [ ] Display current slice number (e.g., "Slice [25 / 49]")
- [ ] Display distance from reference point

### AC3: Direction Selection
- [ ] Toggle buttons for X, Y, Z slice directions
- [ ] X: Streamwise slices (front to back)
- [ ] Y: Lateral slices (side to side)
- [ ] Z: Vertical slices (top to bottom)

### AC4: Field Selection
- [ ] Dropdown for field type:
  - Total Pressure Coefficient (Cp_total)
  - Static Pressure Coefficient (Cp)
  - Total Pressure Coefficient + LIC
  - Velocity magnitude (optional)

### AC5: Display Options
- [ ] Model visibility toggle (show/hide wheel outline)
- [ ] Full-screen mode button
- [ ] Keyboard shortcuts for navigation:
  - ← / → : Previous/Next slice
  - X / Y / Z : Change direction
  - M : Toggle model visibility

---

## Technical Notes

### Data Requirements
Generate slice data from OpenFOAM results:
```bash
# postProcess command
postProcess -func 'surfaces' -latestTime

# surfaces configuration (system/surfaces)
surfaces
{
    type            surfaces;
    libs            (sampling);
    writeControl    writeTime;
    surfaceFormat   vtk;
    fields          (p U);

    surfaces
    {
        xSlice_0
        {
            type        cuttingPlane;
            point       (0 0 0);
            normal      (1 0 0);
        }
        // Repeat for multiple positions
    }
}
```

### Pressure Coefficient Calculation
```
Cp = (p - p_∞) / (0.5 × ρ × V²)

Where:
- p = local static pressure (Pa)
- p_∞ = freestream pressure (Pa)
- ρ = 1.225 kg/m³
- V = freestream velocity (m/s)
```

### Color Scale
AeroCloud uses:
- Range: -0.60 to 1.00
- Color map: Blue (low) → White → Yellow → Red (high)
- Stagnation point (Cp ≈ 1.0): Red
- Separation regions (Cp < 0): Blue

### Reference Implementation
AeroCloud "Slices view" features:
- Large visualization area with CFD contour plot
- Wheel silhouette visible in slice
- Control panel on right side
- Full screen mode available

---

## UI Mockup Specification

```
┌─────────────────────────────────────────────────────────────┐
│ Slices view                                  [⛶ Full screen]│
├─────────────────────────────────┬───────────────────────────┤
│                                 │ Distance: 0.00            │
│                                 │ Slice [25 / 49]           │
│    ┌─────────────────────┐      │                           │
│    │  ████  [WHEEL]  ███ │      │     ◯ (slice indicator)   │
│    │ █████    ◯     ████ │      │     │                     │
│    │██████          █████│      │ ────┼────                 │
│    │ █████          ████ │      │     │                     │
│    │  ████          ███  │      │     ◯                     │
│    │   ███          ██   │      │                           │
│    └─────────────────────┘      │ [████████░░░░░] ← slider  │
│                                 │ [← Previous]  [Next →]    │
│ (Pressure contour plot)         │                           │
│                                 │ ⓘ Keyboard controls       │
├─────────────────────────────────┼───────────────────────────┤
│ Scale:                          │ Options                   │
│ Cp [-]                          │ Field: [Total Pressure ▼] │
│ ■■■■■■■■■■■■■■■■■■■■           │ Direction: [X] [Y] [Z]    │
│ -0.60  -0.20  0.20  0.60  1.00 │ Model: [✓]                │
└─────────────────────────────────┴───────────────────────────┘
```

---

## Definition of Done
- [ ] Slice visualization renders correctly
- [ ] Navigation (slider, buttons, keyboard) works
- [ ] Direction switching (X/Y/Z) works
- [ ] Field selection dropdown works
- [ ] Model toggle works
- [ ] Full-screen mode works
- [ ] Color scale displays correctly
- [ ] Performance acceptable (smooth navigation)
- [ ] Unit tests pass

---

## Estimated Effort
**Story Points**: 13

## Dependencies
- OpenFOAM slice extraction
- Results data storage
- WebGL or Canvas rendering library

## Performance Considerations
- Pre-generate slice images during post-processing
- Or use WebGL for real-time rendering
- Consider lazy loading for 49+ slices

