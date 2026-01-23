# WheelFlow Development Roadmap for Claude Code

## Purpose
This document provides a structured development plan that Claude Code can follow to systematically improve WheelFlow to match and exceed AeroCloud's feature set.

---

## Quick Start for Claude Code

When working on WheelFlow improvements, follow this order:

1. **Read this roadmap** to understand priorities
2. **Check the relevant user story** in `/user_stories/` for acceptance criteria
3. **Review BUGS_AND_UX_ISSUES.md** for known issues to avoid
4. **Reference FEATURE_COMPARISON.md** for target behavior
5. **Reference TECHNICAL_RESEARCH.md** for CFD-specific implementation details

---

## Phase 1: Critical Bug Fixes (Priority: IMMEDIATE)

### 1.1 Fix Navigation Tabs
**Bug Reference**: BUG-001 in BUGS_AND_UX_ISSUES.md

**Problem**: Navigation tabs (Upload, Simulations, Results) don't change the view.

**Implementation Approach**:
```javascript
// In the main App component, add state management for active tab
const [activeView, setActiveView] = useState('upload');

// Navigation buttons should call:
<button onClick={() => setActiveView('upload')}>Upload</button>
<button onClick={() => setActiveView('simulations')}>Simulations</button>
<button onClick={() => setActiveView('results')}>Results</button>

// Conditionally render the appropriate section:
{activeView === 'upload' && <UploadSection />}
{activeView === 'simulations' && <SimulationsSection />}
{activeView === 'results' && <ResultsSection />}
```

**Validation**: After fix, clicking each tab should show only that section's content.

---

### 1.2 Add Basic Error Handling
**Bug Reference**: ERR-001, ERR-002 in BUGS_AND_UX_ISSUES.md

**Implementation**:
- Add try/catch around file upload
- Display user-friendly error messages
- Add error boundary component

---

## Phase 2: Results Display (Priority: HIGH)

### 2.1 Implement Results Dashboard
**User Story**: US-001 in user_stories/US001_RESULTS_DASHBOARD.md

**Key Components to Build**:

```
src/components/Results/
├── ResultsDashboard.jsx      # Main container
├── KeyMetricsCard.jsx        # Force/Coefficient display
├── MetricTypeTabs.jsx        # Force|Coefficient|CdA|Moment tabs
├── InputParametersCard.jsx   # Simulation settings summary
└── ModelPreview3D.jsx        # 3D visualization
```

**Data Structure** (from OpenFOAM):
```javascript
const simulationResults = {
  name: "TTTR28_22_TSV3",
  status: "completed",
  yawAngles: [0, 5, 10, 15, 20],
  results: {
    "0": { Fd: 0.85, Fl: 0.12, Fs: 0.05 },
    "5": { Fd: 0.87, Fl: 0.15, Fs: 0.42 },
    // ... etc
  },
  inputParameters: {
    quality: "standard",
    groundSetting: "slip",
    fluid: "air",
    speed: 13.9,
    wheelRadius: 0.325
  }
};
```

**AeroCloud Reference Values** (for validation):
- Yaw 15.0°: Fd = 0.93 N, Fl = 0.27 N, Fs = 7.87 N
- Quality: STANDARD
- Speed: 13.9 m/s

---

### 2.2 Implement Simulation List
**User Story**: US-002 in user_stories/US002_SIMULATION_LIST.md

**Key Features**:
- Table with columns: Name, Quality, Status, Yaw Angles, Created
- Click row to view results
- Delete with confirmation
- Sort by any column

---

## Phase 3: Visualization (Priority: HIGH)

### 3.1 Force Distribution Graph
**User Story**: US-003 in user_stories/US003_FORCE_DISTRIBUTION_GRAPH.md

**Recommended Library**: Recharts (already common in React projects)

```jsx
import { AreaChart, Area, XAxis, YAxis, Tooltip } from 'recharts';

<AreaChart data={forceDistributionData}>
  <XAxis dataKey="position" label="Position along model [m]" />
  <YAxis label="Cumulative Drag Force [N]" />
  <Area type="monotone" dataKey="cumulativeDrag" fill="#00bcd4" />
</AreaChart>
```

**Data Format**:
```javascript
const forceDistributionData = [
  { position: -0.65, cumulativeDrag: 0.0 },
  { position: -0.60, cumulativeDrag: 0.05 },
  { position: -0.55, cumulativeDrag: 0.15 },
  // ... extracted from OpenFOAM slices
];
```

---

### 3.2 Pressure Slice Visualization
**User Story**: US-004 in user_stories/US004_PRESSURE_SLICE_VIEW.md

**Implementation Options**:
1. **Pre-rendered images**: Generate PNG slices during post-processing
2. **WebGL rendering**: Real-time rendering using Three.js
3. **Canvas 2D**: Simpler approach with heatmap library

**Recommended Approach** (Pre-rendered):
```javascript
// Store slice images during simulation
const slices = {
  x: ["/slices/x_001.png", "/slices/x_002.png", ...],
  y: [...],
  z: [...]
};

// Navigation
const [direction, setDirection] = useState('x');
const [sliceIndex, setSliceIndex] = useState(25);
```

**Color Scale** (match AeroCloud):
- Blue (-0.60) → White (0.20) → Yellow (0.60) → Red (1.00)
- Label: "Total Pressure Coefficient [-]"

---

## Phase 4: Organization & Comparison (Priority: MEDIUM)

### 4.1 Compare Runs Feature
**User Story**: US-005 in user_stories/US005_COMPARE_RUNS.md

**AeroCloud Metrics Displayed**:
| Column | Description |
|--------|-------------|
| Name | Simulation name |
| Yaw | Yaw angle tested |
| Cd | Drag coefficient (sortable) |
| Total heat transfer | W/K |
| Heat transfer coefficient | W/m²K |
| Surface area | m² |

**Filters Needed**:
- Yaw angle dropdown (e.g., "10.0")
- Quality filter (All/Basic/Standard/Pro)
- Name search field

---

### 4.2 Project Organization
**User Story**: US-006 in user_stories/US006_PROJECT_ORGANIZATION.md

**Data Model**:
```javascript
const project = {
  id: "master-testing",
  name: "Master Testing",
  description: "Wheel designs for 2025 season",
  status: "active", // or "archived"
  simulations: ["sim-001", "sim-002", ...],
  createdAt: "2025-03-11",
  updatedAt: "2025-03-12"
};
```

---

## Phase 5: Export & Polish (Priority: MEDIUM)

### 5.1 Export Reports
**User Story**: US-007 in user_stories/US007_EXPORT_REPORTS.md

**PDF Generation** (using jsPDF):
```javascript
import jsPDF from 'jspdf';

const generateReport = (simulation) => {
  const doc = new jsPDF();
  doc.text('WheelFlow Simulation Report', 20, 20);
  doc.text(`Name: ${simulation.name}`, 20, 40);
  // Add metrics table, charts as images
  doc.save(`${simulation.name}_report.pdf`);
};
```

**Excel Export** (using SheetJS):
```javascript
import * as XLSX from 'xlsx';

const exportToExcel = (simulation) => {
  const ws = XLSX.utils.json_to_sheet(simulation.results);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Results");
  XLSX.writeFile(wb, `${simulation.name}_data.xlsx`);
};
```

---

## Implementation Checklist

### Phase 1 Checklist
- [ ] Fix navigation tab switching
- [ ] Add error boundary component
- [ ] Add file upload error handling
- [ ] Add simulation failure handling

### Phase 2 Checklist
- [ ] Create ResultsDashboard component
- [ ] Implement KeyMetricsCard with tabs
- [ ] Implement InputParametersCard
- [ ] Create SimulationsList component
- [ ] Add simulation status tracking

### Phase 3 Checklist
- [ ] Integrate Recharts library
- [ ] Implement ForceDistributionGraph
- [ ] Create SliceViewer component
- [ ] Add slice navigation controls
- [ ] Implement color scale legend

### Phase 4 Checklist
- [ ] Create CompareRuns view
- [ ] Implement comparison table
- [ ] Add filtering controls
- [ ] Create Project model
- [ ] Implement project CRUD operations

### Phase 5 Checklist
- [ ] Add jsPDF dependency
- [ ] Implement PDF report generation
- [ ] Add SheetJS dependency
- [ ] Implement Excel export
- [ ] Add download buttons to UI

---

## Testing Strategy

### Unit Tests
- Test coefficient calculations
- Test data parsing from OpenFOAM output
- Test component rendering

### Integration Tests
- Test full simulation workflow
- Test navigation between views
- Test export functionality

### Visual Regression Tests
- Compare screenshots before/after changes
- Verify color schemes match design

---

## Reference URLs

**WheelFlow (Your App)**:
https://containing-loving-donate-hats.trycloudflare.com/

**AeroCloud (Target Reference)**:
https://aerocloud.nablaflow.io/v7/simulations/15-tttr28-22-wakehalo-06aok2q4ttrl5703jc1m75jb5s

**AeroCloud Compare Runs**:
https://aerocloud.nablaflow.io/v7/projects/master-testing-4c0bc3/completed-runs

---

## Success Metrics

After implementing all phases, WheelFlow should:

1. ✅ Display simulation results with key metrics
2. ✅ Show force distribution graphs
3. ✅ Visualize pressure coefficient slices
4. ✅ Compare multiple simulation runs
5. ✅ Export PDF reports and Excel data
6. ✅ Organize simulations into projects

**Unique WheelFlow Advantages to Preserve**:
- Local GPU acceleration (RTX 3090)
- Wheel rotation toggle
- Wheel radius input
- Dark theme aesthetic
- No cloud dependency

