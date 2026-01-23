# User Story: US-006 - Project-Based Organization

## Title
Organize Simulations into Projects

## Priority
**MEDIUM** - Important for workflow management

## User Story
As a **wheel engineer working on multiple products**, I want to **organize my simulations into separate projects** so that I can **keep my work organized and easily find simulations for a specific wheel design**.

---

## Acceptance Criteria

### AC1: Project Management
- [ ] Create new project with name and optional description
- [ ] Edit project name and description
- [ ] Delete project (with confirmation, moves simulations to "Uncategorized")
- [ ] View list of all projects

### AC2: Project List View
- [ ] Show project name
- [ ] Show simulation count per project
- [ ] Show last updated date
- [ ] Show project status (Active/Archived)
- [ ] Filter by status (Active/Archived/All)

### AC3: Simulation Association
- [ ] Assign simulation to a project during creation
- [ ] Move simulation between projects
- [ ] Create simulation directly from project view
- [ ] Default "Uncategorized" project for orphan simulations

### AC4: Navigation
- [ ] Breadcrumb navigation: Projects > [Project Name] > [Simulation Name]
- [ ] Click project to see its simulations
- [ ] Back navigation to project list

---

## Technical Notes

### Data Model
```typescript
interface Project {
  id: string;
  name: string;
  description?: string;
  status: 'active' | 'archived';
  createdAt: Date;
  updatedAt: Date;
  simulationCount: number;
}

interface Simulation {
  // ... existing fields
  projectId: string | null;
}
```

### Reference Implementation
AeroCloud project structure:
- Sidebar shows "Latest projects" with quick access
- Main content shows project list table
- Projects have "Active" badge status
- Click project → shows simulation list within project

---

## UI Mockup Specification

```
┌─────────────────────────────────────────────────────────────┐
│ Projects                                    [+ New Project] │
├─────────────────────────────────────────────────────────────┤
│ [Active] [Archived] [All]                                   │
├─────────────────────────────────────────────────────────────┤
│ Active projects (2)                                         │
├─────────────────────────────────────────────────────────────┤
│ Name                    │ Simulations │ Status  │ Updated   │
├─────────────────────────┼─────────────┼─────────┼───────────┤
│ 📁 TTTR28 Development   │     6       │ Active  │ Jan 23    │
│ 📁 MachEvo R&D          │     3       │ Active  │ Jan 20    │
└─────────────────────────┴─────────────┴─────────┴───────────┘
```

### Project Detail View
```
┌─────────────────────────────────────────────────────────────┐
│ Projects > TTTR28 Development                               │
├─────────────────────────────────────────────────────────────┤
│ TTTR28 Development                         [+ New Simulation]│
│ Wheel designs for 2025 triathlon season                     │
├─────────────────────────────────────────────────────────────┤
│ [Simulations] [Compare Runs]                    [Search...] │
├─────────────────────────────────────────────────────────────┤
│ Name              │ Quality  │ Status    │ Yaws     │Created│
├───────────────────┼──────────┼───────────┼──────────┼───────┤
│ TTTR28_22_TSV3    │ STANDARD │ Completed │ 15.0°    │Jan 23 │
│ TTTR28_22_WakeHalo│ STANDARD │ Completed │ 0°,5°,10°│Jan 22 │
└───────────────────┴──────────┴───────────┴──────────┴───────┘
```

---

## Definition of Done
- [ ] Projects can be created, edited, deleted
- [ ] Project list displays correctly
- [ ] Simulations can be assigned to projects
- [ ] Navigation between projects and simulations works
- [ ] Filtering by status works
- [ ] Unit tests pass

---

## Estimated Effort
**Story Points**: 8

## Dependencies
- Simulation list (US-002) - extends data model

## Future Enhancements
- Project templates
- Project sharing/collaboration
- Project-level settings (default parameters)

