# User Story: US-005 - Compare Simulation Runs

## Title
Compare Multiple Wheel Simulations Side-by-Side

## Priority
**HIGH** - Essential for design iteration

## User Story
As a **wheel designer**, I want to **compare the results of multiple simulations side-by-side** so that I can **evaluate design changes and select the best performing wheel**.

---

## Acceptance Criteria

### AC1: Comparison Table
- [ ] Display selected simulations in table format
- [ ] Show simulation name
- [ ] Display yaw angle for each row
- [ ] Show key metrics: Cd, CdA, Fd, Fl, Fs
- [ ] Support additional columns: Heat transfer, Surface area

### AC2: Selection & Filtering
- [ ] Checkbox to select simulations for comparison
- [ ] Filter by yaw angle (dropdown)
- [ ] Filter by mesh quality (All / Basic / Standard / Pro)
- [ ] Search by simulation name

### AC3: Sorting
- [ ] Sort by any column (ascending/descending)
- [ ] Default sort by drag coefficient (Cd)
- [ ] Visual indicator for sorted column

### AC4: Visual Comparison (Future)
- [ ] Side-by-side pressure plots
- [ ] Overlay force distribution graphs
- [ ] Delta/difference visualization

---

## Technical Notes

### Data Model
```typescript
interface ComparisonRow {
  simulationId: string;
  simulationName: string;
  yawAngle: number;
  meshQuality: 'basic' | 'standard' | 'pro';
  metrics: {
    dragForce: number;      // Fd [N]
    liftForce: number;      // Fl [N]
    sideForce: number;      // Fs [N]
    dragCoefficient: number; // Cd [-]
    dragArea: number;       // CdA [m²]
    heatTransfer?: number;  // [W/K]
    surfaceArea?: number;   // [m²]
  };
}
```

### Reference Implementation
AeroCloud "Compare Runs" tab shows:
- Table with columns: Name, Yaw, Cd↑, Total heat transfer, Heat transfer coefficient, Surface area
- Row selection checkboxes
- Filters at top: Yaw angle dropdown, Quality filter, Name search
- "Display" button for customization

### Comparison Best Practices
From Bramble CFD research:
- **Switcher tool** - Toggle between runs to see subtle differences
- **Delta plots** - Show differences between simulations
- Focus on same yaw angle for fair comparison

---

## UI Mockup Specification

```
┌─────────────────────────────────────────────────────────────┐
│ Compare Runs (3)                                            │
├─────────────────────────────────────────────────────────────┤
│ Yaw: [10.0° ▼]  Quality: [All qualities ▼]  [Search...]    │
├─────────────────────────────────────────────────────────────┤
│ □ │ Name              │ Yaw   │ Cd ↑  │ CdA      │ Fd      │
├───┼───────────────────┼───────┼───────┼──────────┼─────────┤
│ ☑ │ TTTR28_21_MachEvo │ 10.0° │ 0.051 │ 0.0079m² │ 0.93 N  │
│ ☑ │ TTTR28_22_WakeHalo│ 10.0° │ 0.144 │ 0.0225m² │ 0.95 N  │
│ ☑ │ TTTR28_22_TSV3    │ 10.0° │ 0.270 │ 0.0421m² │ 1.02 N  │
└───┴───────────────────┴───────┴───────┴──────────┴─────────┘

Selected: 3 simulations
[📊 Compare Visually]  [📥 Export Comparison]
```

---

## Definition of Done
- [ ] Comparison table displays correctly
- [ ] Filtering by yaw angle works
- [ ] Filtering by quality works
- [ ] Search filters results
- [ ] Sorting works on all columns
- [ ] Multiple simulations can be selected
- [ ] Unit tests pass

---

## Estimated Effort
**Story Points**: 8

## Dependencies
- Simulation list (US-002)
- Results storage with queryable metrics

## Future Enhancements
- Visual comparison mode (side-by-side plots)
- Delta calculation between two selected runs
- Export comparison as PDF/CSV

