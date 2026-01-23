# WheelFlow Development Plan
## Comprehensive Improvements & Visualization Features

**Goal:** Match AeroCloud capabilities for bicycle wheel CFD analysis

---

## Current State vs Target

| Feature | Current | Target | Priority |
|---------|---------|--------|----------|
| Mesh Resolution | ~60k cells | 6-8M cells | User-controlled |
| Solver | simpleFoam (steady) | pimpleFoam + AMI (transient) | P1 |
| Wheel Rotation | Static wall | AMI rotating mesh | P1 |
| Ground | Fixed wall | Moving belt (freestream velocity) | P2 |
| Yaw Angles | Single (0°) | Multi-angle batch (0°-20°) | P2 |
| Reference Area | Fixed 0.1 m² | Calculated frontal area | P2 |
| Visualizations | None | 5 types (see below) | P1 |
| Results Page | Basic JSON | Interactive dashboard | P1 |

---

## Phase 1: Core Physics Improvements

### 1.1 AMI Rotating Mesh (Critical)
**Impact:** 2.2% drag difference between static and rotating wheel

**Files to modify:**
- `backend/app.py` - Add AMI mesh generation
- New: `backend/openfoam_templates/dynamicMeshDict.py`
- New: `backend/openfoam_templates/createPatchDict.py`

**Implementation:**
```
1. Generate AMI_cylinder.stl around wheel (cylindrical envelope)
2. Add dynamicMeshDict for solidBody rotation
3. Create AMI patches with createPatch utility
4. Switch solver to pimpleFoam for transient simulation
5. Add cyclicAMI boundary conditions to all field files
```

**dynamicMeshDict template:**
```cpp
dynamicFvMesh   dynamicMotionSolverFvMesh;
motionSolverLibs ("libfvMotionSolvers.so");
motionSolver    solidBody;
cellZone        rotatingZone;
solidBodyMotionFunction rotatingMotion;
rotatingMotionCoeffs
{
    origin      (0 0 {wheel_center_z});
    axis        (0 1 0);  // Y-axis rotation
    omega       constant {omega};  // rad/s = V/R
}
```

**Rotation speed:** ω = V/R = 13.9/0.325 = 42.77 rad/s

### 1.2 Moving Ground Belt
**Impact:** 1.0-1.8% drag reduction vs fixed ground

**Current:** Ground has `fixedValue` with freestream velocity (partially correct)
**Fix needed:** Ensure ground moves at exact freestream velocity in all directions

**Files to modify:**
- `backend/app.py` - Update ground boundary condition

**Ground BC for U:**
```cpp
ground
{
    type            movingWallVelocity;
    value           uniform ({vx} {vy} 0);
}
```

### 1.3 Multi-Yaw Angle Batch Processing
**Target:** Run simulations at 0°, 5°, 10°, 15°, 20° yaw

**Implementation approach:**
```
Option A: Sequential runs (simpler)
- Run each yaw angle as separate case
- Share mesh, only change boundary conditions
- Parallel execution on different CPU cores

Option B: Single transient simulation (complex)
- Use arbitraryPatch inlet
- Change inlet direction over time
- Extract time-averaged results at each yaw
```

**Recommended:** Option A - Sequential with shared mesh

**Files to modify:**
- `backend/app.py` - Loop over yaw angles
- Add `POST /api/simulate/batch` endpoint
- Store results per yaw angle

**Velocity components at yaw:**
```python
def velocity_components(speed, yaw_deg):
    yaw_rad = math.radians(yaw_deg)
    return (
        speed * math.cos(yaw_rad),  # Vx
        speed * math.sin(yaw_rad),  # Vy
        0.0                          # Vz
    )
```

### 1.4 Reference Area Calculation
**Current:** Fixed Aref = 0.1 m²
**Target:** Calculate actual frontal area from STL geometry

**Implementation:**
```python
def calculate_frontal_area(stl_path, direction='x'):
    """
    Project STL geometry onto plane perpendicular to flow
    and calculate enclosed area using convex hull or alpha shape
    """
    # 1. Load STL vertices
    # 2. Project onto YZ plane (for x-direction flow)
    # 3. Calculate convex hull area
    # 4. Return area in m²
```

**Typical values:**
- AeroCloud uses Aref = 0.0225 m² for bicycle wheel
- This gives Cd = 0.490 for Fd = 1.31 N

---

## Phase 2: Visualization System

### 2.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Results Page                          │
├─────────────┬─────────────┬─────────────┬───────────────┤
│ Hero Image  │ Force Dist  │ 3D Pressure │ Slices View   │
│ (PNG)       │ (Chart.js)  │ (Three.js)  │ (Canvas)      │
├─────────────┴─────────────┴─────────────┴───────────────┤
│                  Parts Breakdown (Chart.js)              │
└─────────────────────────────────────────────────────────┘
         ↑                    ↑                    ↑
    ParaView             Python              OpenFOAM
    headless            matplotlib          postProcess
```

### 2.2 Hero Image (3D Streamlines)
**Source:** ParaView headless rendering
**Output:** PNG image (1920x1080)

**Implementation:**
```python
# backend/visualization/hero_image.py

def generate_hero_image(case_dir: Path, output_path: Path):
    """Generate 3D streamline visualization using ParaView"""

    pvpython_script = '''
from paraview.simple import *

# Load OpenFOAM case
foam = OpenFOAMReader(FileName='{case_dir}/case.foam')
foam.MeshRegions = ['internalMesh']
foam.CellArrays = ['U', 'p']

# Create streamlines
stream = StreamTracer(Input=foam, SeedType='Point Cloud')
stream.SeedType.Center = [0.0, 0.0, 0.3]
stream.SeedType.Radius = 0.5
stream.SeedType.NumberOfPoints = 200
stream.MaximumStreamlineLength = 3.0

# Color by velocity magnitude
ColorBy(stream, ('POINTS', 'U', 'Magnitude'))

# Setup render view
view = GetActiveViewOrCreate('RenderView')
view.ViewSize = [1920, 1080]
view.Background = [0.1, 0.1, 0.15]

# Camera position (isometric view of wheel)
view.CameraPosition = [1.5, -2.0, 1.0]
view.CameraFocalPoint = [0.0, 0.0, 0.3]
view.CameraViewUp = [0, 0, 1]

# Add wheel surface
wheelDisplay = Show(foam, view)
wheelDisplay.Representation = 'Surface'
wheelDisplay.DiffuseColor = [0.8, 0.8, 0.8]

# Save screenshot
SaveScreenshot('{output_path}', view)
'''

    # Run ParaView in headless mode
    subprocess.run(['pvpython', '-c', pvpython_script], check=True)
```

**Dependencies:** ParaView with pvpython, osmesa for headless rendering

### 2.3 Force Distribution Chart
**Source:** forceCoeffs postProcessing data
**Output:** Interactive Chart.js line chart

**Data extraction:**
```python
# backend/visualization/force_distribution.py

def extract_force_distribution(case_dir: Path) -> dict:
    """Extract cumulative force along wheel length"""

    # Run OpenFOAM wallShearStress postProcess
    # Parse surface force data
    # Bin by x-position and accumulate

    return {
        "positions": [0.05, 0.10, ...],  # meters
        "cumulative_drag": [0.1, 0.25, ...],  # Newtons
        "cumulative_lift": [...],
        "cumulative_side": [...]
    }
```

**Frontend component:**
```javascript
// static/js/charts/force-distribution.js

function renderForceDistribution(data, canvasId) {
    const ctx = document.getElementById(canvasId).getContext('2d');

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.positions,
            datasets: [{
                label: 'Cumulative Drag (N)',
                data: data.cumulative_drag,
                fill: true,
                backgroundColor: 'rgba(54, 162, 235, 0.2)',
                borderColor: 'rgba(54, 162, 235, 1)',
            }]
        },
        options: {
            scales: {
                x: { title: { display: true, text: 'Position (m)' }},
                y: { title: { display: true, text: 'Force (N)' }}
            }
        }
    });
}
```

### 2.4 Pressure Slices
**Source:** OpenFOAM cuttingPlane function object
**Output:** Canvas-rendered 2D contour plots

**Implementation:**
```cpp
// Add to controlDict functions section
cuttingPlane
{
    type            surfaces;
    libs            (sampling);
    writeControl    writeTime;
    surfaceFormat   raw;
    fields          (p U);

    surfaces
    {
        slice_x0
        {
            type        cuttingPlane;
            planeType   pointAndNormal;
            pointAndNormalDict
            {
                point   (0 0 0.3);
                normal  (1 0 0);
            }
            interpolate true;
        }
        // Add more slices at x = -0.2, 0.2, 0.5, 1.0, etc.
    }
}
```

**Frontend:**
```javascript
// static/js/charts/pressure-slice.js

function renderPressureSlice(sliceData, canvasId) {
    const canvas = document.getElementById(canvasId);
    const ctx = canvas.getContext('2d');

    // sliceData: { y: [], z: [], p: [] }
    // Render as colored points/interpolated grid
    // Use viridis colormap
    // Range: Cp from -0.6 to 1.0
}
```

### 2.5 3D Interactive Pressure Map
**Source:** VTK export from ParaView
**Output:** Three.js WebGL viewer with pressure coloring

**Data pipeline:**
```
OpenFOAM case → ParaView → Export VTK/PLY → Load in Three.js
```

**Backend export:**
```python
# backend/visualization/export_3d.py

def export_pressure_surface(case_dir: Path, output_path: Path):
    """Export wheel surface with pressure values for Three.js"""

    # ParaView script to export colored surface
    script = '''
from paraview.simple import *

foam = OpenFOAMReader(FileName='{case_dir}/case.foam')
foam.MeshRegions = ['wheel']
foam.CellArrays = ['p']

# Extract surface
extractSurface = ExtractSurface(Input=foam)

# Save as PLY with vertex colors
SaveData('{output_path}', extractSurface,
         ColorArrayName=['POINTS', 'p'])
'''
```

**Frontend loader:**
```javascript
// static/js/viewers/pressure-3d.js

async function loadPressureModel(plyPath, containerId) {
    const loader = new THREE.PLYLoader();
    const geometry = await loader.loadAsync(plyPath);

    // Apply pressure colormap to vertex colors
    const material = new THREE.MeshPhongMaterial({
        vertexColors: true,
        side: THREE.DoubleSide
    });

    const mesh = new THREE.Mesh(geometry, material);
    scene.add(mesh);

    // Add colorbar legend
    addColorbar(container, { min: -0.6, max: 1.0, label: 'Cp' });
}
```

### 2.6 Parts Breakdown Bar Chart
**Source:** Multiple forceCoeffs function objects per surface region
**Output:** Horizontal bar chart showing component contributions

**Implementation:**
```cpp
// controlDict - separate forceCoeffs per part
forceCoeffs_rim
{
    type            forceCoeffs;
    libs            (forces);
    patches         (rim);
    // ... same settings
}

forceCoeffs_tire
{
    type            forceCoeffs;
    libs            (forces);
    patches         (tire);
    // ... same settings
}

forceCoeffs_spokes
{
    type            forceCoeffs;
    libs            (forces);
    patches         (spokes);
    // ... same settings
}
```

**Note:** Requires STL with named regions or multiple STL files

---

## Phase 3: Interactive Results Page

### 3.1 New Results Page Layout

```html
<!-- templates/results.html -->

<div class="results-dashboard">
    <!-- Header with key metrics -->
    <div class="metrics-bar">
        <div class="metric">
            <span class="metric-label">Drag Force</span>
            <span class="metric-value">1.31 N</span>
        </div>
        <div class="metric">
            <span class="metric-label">CdA</span>
            <span class="metric-value">0.011 m²</span>
        </div>
        <div class="metric">
            <span class="metric-label">Side Force</span>
            <span class="metric-value">14.10 N</span>
        </div>
        <div class="metric">
            <span class="metric-label">Yaw Moment</span>
            <span class="metric-value">4.34 Nm</span>
        </div>
    </div>

    <!-- Main visualization grid -->
    <div class="viz-grid">
        <div class="viz-card hero">
            <h3>Flow Visualization</h3>
            <img id="hero-image" src="/api/jobs/{id}/viz/hero.png">
        </div>

        <div class="viz-card">
            <h3>Force Distribution</h3>
            <canvas id="force-chart"></canvas>
        </div>

        <div class="viz-card wide">
            <h3>3D Pressure Map</h3>
            <div id="pressure-3d-viewer"></div>
            <div class="viewer-controls">
                <button onclick="resetCamera3D()">Reset</button>
                <select id="field-select">
                    <option value="p">Pressure</option>
                    <option value="U">Velocity</option>
                </select>
            </div>
        </div>

        <div class="viz-card">
            <h3>Pressure Slices</h3>
            <div class="slice-controls">
                <input type="range" id="slice-position" min="-0.5" max="2" step="0.1">
                <span id="slice-pos-label">x = 0.0 m</span>
            </div>
            <canvas id="slice-canvas"></canvas>
        </div>

        <div class="viz-card">
            <h3>Parts Breakdown</h3>
            <canvas id="parts-chart"></canvas>
        </div>
    </div>

    <!-- Yaw angle comparison (if multi-angle run) -->
    <div class="yaw-comparison" id="yaw-section">
        <h3>Yaw Angle Analysis</h3>
        <div class="yaw-tabs">
            <button class="yaw-tab active" data-yaw="0">0°</button>
            <button class="yaw-tab" data-yaw="5">5°</button>
            <button class="yaw-tab" data-yaw="10">10°</button>
            <button class="yaw-tab" data-yaw="15">15°</button>
            <button class="yaw-tab" data-yaw="20">20°</button>
        </div>
        <canvas id="yaw-polar-chart"></canvas>
    </div>

    <!-- Export options -->
    <div class="export-bar">
        <button onclick="exportPDF()">Download Report (PDF)</button>
        <button onclick="exportCSV()">Export Data (CSV)</button>
        <button onclick="exportImages()">Download Images (ZIP)</button>
    </div>
</div>
```

### 3.2 New API Endpoints

```python
# backend/app.py - New endpoints

@app.get("/api/jobs/{job_id}/viz/hero.png")
async def get_hero_image(job_id: str):
    """Return pre-generated hero image"""
    path = CASES_DIR / job_id / "visualizations" / "hero.png"
    return FileResponse(path, media_type="image/png")

@app.get("/api/jobs/{job_id}/viz/pressure_surface.ply")
async def get_pressure_surface(job_id: str):
    """Return 3D pressure surface for Three.js"""
    path = CASES_DIR / job_id / "visualizations" / "pressure_surface.ply"
    return FileResponse(path)

@app.get("/api/jobs/{job_id}/viz/force_distribution")
async def get_force_distribution(job_id: str):
    """Return force distribution data as JSON"""
    # Parse postProcessing data
    return {"positions": [...], "cumulative_drag": [...], ...}

@app.get("/api/jobs/{job_id}/viz/slices/{position}")
async def get_slice(job_id: str, position: float):
    """Return pressure slice data at given x position"""
    return {"y": [...], "z": [...], "p": [...], "U": [...]}

@app.get("/api/jobs/{job_id}/viz/parts_breakdown")
async def get_parts_breakdown(job_id: str):
    """Return force breakdown by component"""
    return {
        "parts": ["rim", "tire", "spokes"],
        "drag": [0.4, 0.6, 0.31],
        "side": [5.0, 7.0, 2.1]
    }
```

---

## Phase 4: Implementation Order

### Sprint 1: Foundation (Week 1-2)
1. [ ] Fix reference area calculation (frontal area from STL)
2. [ ] Update ground BC to proper movingWallVelocity
3. [ ] Add mesh quality presets (basic/standard/pro cell counts)
4. [ ] Create visualization directory structure

### Sprint 2: Visualizations - Part 1 (Week 2-3)
5. [ ] Install ParaView with pvpython and osmesa
6. [ ] Implement hero image generation
7. [ ] Implement force distribution extraction and Chart.js
8. [ ] Add pressure slices function object

### Sprint 3: Visualizations - Part 2 (Week 3-4)
9. [ ] Implement 3D pressure export (PLY)
10. [ ] Create Three.js pressure viewer
11. [ ] Implement slice visualization with Canvas
12. [ ] Create interactive results page template

### Sprint 4: AMI Rotation (Week 4-5)
13. [ ] Create AMI cylinder STL generator
14. [ ] Implement dynamicMeshDict generation
15. [ ] Implement createPatchDict generation
16. [ ] Switch to pimpleFoam solver
17. [ ] Update all boundary conditions for AMI

### Sprint 5: Multi-Yaw & Polish (Week 5-6)
18. [ ] Implement batch yaw angle processing
19. [ ] Add yaw comparison charts (polar plot)
20. [ ] Implement parts breakdown (requires multi-region STL)
21. [ ] Add PDF/CSV export functionality
22. [ ] Testing and validation against AeroCloud

---

## Dependencies

### System Requirements
- ParaView 5.10+ with pvpython
- osmesa (for headless rendering)
- Python packages: numpy, matplotlib, vtk

### JavaScript Libraries (CDN)
- Three.js r128+ with PLYLoader
- Chart.js 4.x
- (optional) D3.js for custom visualizations

### OpenFOAM Utilities
- snappyHexMesh
- pimpleFoam (instead of simpleFoam)
- createPatch
- postProcess

---

## Validation Targets

From AeroCloud TTTR28_22_TSV3 at 15° yaw:

| Metric | Target | Tolerance |
|--------|--------|-----------|
| Drag Force | 1.31 N | ±5% |
| Side Force | 14.10 N | ±5% |
| Cd | 0.490 | ±5% |
| Cs | 5.253 | ±5% |
| Yaw Moment | 4.34 Nm | ±10% |

---

## File Structure After Implementation

```
wheelflow/
├── backend/
│   ├── app.py                    # Main FastAPI app
│   ├── stl_validator.py          # STL processing
│   ├── frontal_area.py           # NEW: Area calculation
│   ├── visualization/            # NEW
│   │   ├── __init__.py
│   │   ├── hero_image.py         # ParaView streamlines
│   │   ├── force_distribution.py # Force data extraction
│   │   ├── pressure_slices.py    # Slice extraction
│   │   ├── pressure_surface.py   # 3D export
│   │   └── parts_breakdown.py    # Component forces
│   └── openfoam_templates/       # NEW
│       ├── __init__.py
│       ├── dynamic_mesh.py       # AMI config
│       ├── create_patch.py       # AMI patches
│       └── pimple_settings.py    # Transient solver
├── static/
│   ├── css/
│   │   ├── style.css
│   │   └── results.css           # NEW
│   └── js/
│       ├── app.js
│       ├── charts/               # NEW
│       │   ├── force-distribution.js
│       │   ├── parts-breakdown.js
│       │   └── yaw-polar.js
│       └── viewers/              # NEW
│           ├── pressure-3d.js    # Three.js viewer
│           └── slice-viewer.js   # Canvas slice
├── templates/
│   ├── index.html
│   └── results.html              # NEW: Interactive results
└── cases/{job_id}/
    └── visualizations/           # NEW: Generated viz
        ├── hero.png
        ├── pressure_surface.ply
        └── slices/
            ├── slice_x-0.2.json
            ├── slice_x0.0.json
            └── ...
```

---

## Notes

1. **ParaView headless rendering** requires osmesa or EGL. On Ubuntu:
   ```bash
   apt-get install paraview python3-paraview libosmesa6
   ```

2. **AMI mesh generation** is complex - start with MRF (Moving Reference Frame)
   as a simpler alternative that still captures rotation effects

3. **Parts breakdown** requires either:
   - Multiple STL files (rim.stl, tire.stl, spokes.stl)
   - Single STL with named solid regions
   - Current TTTR28 STL is single part - may need to skip or simplify

4. **Mesh quality presets** suggested cell counts:
   - Basic: 500k cells (~5 min)
   - Standard: 2M cells (~20 min)
   - Pro: 6-8M cells (~2 hours)
