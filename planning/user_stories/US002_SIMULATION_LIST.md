# User Story: US-002 - Simulation List View

## Title
View and Manage Past Simulations

## Priority
**HIGH** - Essential for usability

## User Story
As a **wheel designer**, I want to **see a list of all my past simulations** so that I can **easily access previous results and track my design iterations**.

---

## Acceptance Criteria

### AC1: Simulation List Display
- [ ] Show all completed simulations in a list/table view
- [ ] Display simulation name
- [ ] Show creation date/time
- [ ] Display status (Pending, Running, Completed, Failed)
- [ ] Show mesh quality (Basic/Standard/Pro badge)
- [ ] Display yaw angles tested

### AC2: List Interactions
- [ ] Click simulation row to view results
- [ ] Sort by name (A-Z, Z-A)
- [ ] Sort by date (newest/oldest)
- [ ] Search/filter by simulation name

### AC3: Simulation Management
- [ ] Delete simulation (with confirmation dialog)
- [ ] Rename simulation
- [ ] Duplicate simulation parameters for new run

### AC4: Empty State
- [ ] Show helpful message when no simulations exist
- [ ] Provide call-to-action to create first simulation
- [ ] Display "Upload Geometry" button

---

## Technical Notes

### Data Model
```typescript
interface Simulation {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  meshQuality: 'basic' | 'standard' | 'pro';
  yawAngles: number[];
  speed: number;
  wheelRadius: number;
  groundEnabled: boolean;
  groundType: 'slip' | 'moving';
  createdAt: Date;
  completedAt?: Date;
  results?: SimulationResults;
}
```

### Reference Implementation
AeroCloud shows simulations in a table with columns:
- Name (with icon)
- Quality (badge: STANDARD)
- Status (badge: Completed with green dot)
- Yaws (e.g., "0.0°, 10.0°" or "15.0°")
- Created (date)
- Actions (delete icon)

### Screenshot Reference
See: AeroCloud Master Testing project view showing:
- 6 simulations in list format
- Searchable
- Sortable by "Created" column
- Each row clickable to view details

---

## UI Mockup Specification

```
┌─────────────────────────────────────────────────────────────┐
│ Simulations                                    [+ New Run]  │
├─────────────────────────────────────────────────────────────┤
│ [Search simulations...]                                     │
├─────────────────────────────────────────────────────────────┤
│ Name              │ Quality  │ Status    │ Yaws    │ Created│
├───────────────────┼──────────┼───────────┼─────────┼────────┤
│ TTTR28_22_TSV3    │ STANDARD │ ●Completed│ 0°,5°,10│ Jan 23 │
│ WakeHalo_Test1    │ PRO      │ ●Running  │ 15°     │ Jan 22 │
│ MachEvo_Final     │ BASIC    │ ●Completed│ 0°-20°  │ Jan 21 │
└─────────────────────────────────────────────────────────────┘
```

---

## Definition of Done
- [ ] Simulation list displays all saved simulations
- [ ] Sorting works correctly
- [ ] Search filters results
- [ ] Click navigation to results works
- [ ] Delete with confirmation works
- [ ] Empty state displays correctly
- [ ] Unit tests pass

---

## Estimated Effort
**Story Points**: 5

## Dependencies
- Simulation storage/database mechanism
- Results dashboard (US-001) for navigation target

