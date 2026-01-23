# User Story: US-001 - Results Dashboard

## Title
Display Simulation Results Dashboard with Key Metrics

## Priority
**CRITICAL** - Essential for MVP

## User Story
As a **wheel aerodynamicist**, I want to **see a comprehensive results dashboard after my simulation completes** so that I can **quickly understand the aerodynamic performance of my wheel design**.

---

## Acceptance Criteria

### AC1: Key Metrics Display
- [ ] Display drag force (Fd) in Newtons
- [ ] Display lift force (Fl) in Newtons
- [ ] Display side force (Fs) in Newtons
- [ ] Show all values for each simulated yaw angle
- [ ] Format numbers to appropriate precision (2-3 decimal places)

### AC2: Metric Type Selector
- [ ] Toggle between Force, Coefficient, Coefficient x Area, and Moment views
- [ ] Recalculate and display values when switching modes
- [ ] Coefficient values: Cd, Cl, Cs (dimensionless)
- [ ] CdA values in m² (drag area)
- [ ] Moment values in Nm

### AC3: Input Parameters Summary
- [ ] Display simulation name
- [ ] Show mesh quality setting (Basic/Standard/Pro)
- [ ] Show ground setting (Slip/Moving Belt)
- [ ] Display fluid type (Air)
- [ ] Show input speed in m/s
- [ ] Display yaw angle(s) tested
- [ ] Show number of parts in geometry

### AC4: Visual Design
- [ ] Match existing WheelFlow dark theme
- [ ] Use consistent blue accent colors
- [ ] Display data in a clean, tabular format
- [ ] Include appropriate labels and units

---

## Technical Notes

### Data Requirements
From OpenFOAM simulation output, extract:
- `forces/0/forces.dat` - Force components
- `forces/0/moment.dat` - Moment components
- Calculate coefficients using: `C = F / (0.5 * ρ * V² * A)`

### Reference Implementation
AeroCloud displays metrics in a card layout with:
- Metric type tabs (Force | Coefficient | Coefficient x Area | Moment | Heat transfer)
- Table showing: Yaw angle | Fd | Fl | Fs

### Screenshot Reference
See: AeroCloud simulation results view - Key metrics section displays:
- Tabbed interface for metric types
- Yaw: 15.0 | Fd: 0.93 N | Fl: 0.27 N | Fs: 7.87 N

---

## Definition of Done
- [ ] Results dashboard renders after simulation completion
- [ ] All force components display correctly
- [ ] Coefficient calculations are accurate
- [ ] Metric type switching works
- [ ] Input parameters are shown
- [ ] Unit tests pass
- [ ] Visual design approved

---

## Estimated Effort
**Story Points**: 8

## Dependencies
- Simulation execution must complete successfully
- OpenFOAM force output files must be parsed
- Results storage mechanism needed

