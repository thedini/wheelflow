# Bicycle Wheel Aerodynamic Analysis
## OpenFOAM CFD Workflow for Tire/Rim Optimization

---

## 0. Project Scope & Naming Convention

### Naming Convention
```
TTTR28_22_TSV3
  │    │   └── Wheel model (TSV3, TSV4, etc.)
  │    └────── Rim hook width (21, 22, 23, 24mm)
  └─────────── Tire model + nominal width (Continental TTTR 28mm)
```

### The Problem
- **Inflated tire width ≠ advertised width** — actual shape depends on rim hook width
- **Leading edge profile changes** with each tire/rim combination
- **Aerodynamic performance varies** — need to test all combinations

### Test Matrix
| Tire | Rim Hooks | Wheel Models | Total Combinations |
|------|-----------|--------------|-------------------|
| TTTR25 | 21, 22, 23, 24mm | TSV3, TSV4, ... | 4 × N wheels |
| TTTR28 | 21, 22, 23, 24mm | TSV3, TSV4, ... | 4 × N wheels |
| TTTR30 | 21, 22, 23, 24mm | TSV3, TSV4, ... | 4 × N wheels |

### Workflow Goal
**Input:** STL geometry file (named per convention)
**Output:**
- Drag force (N) and CdA (m²)
- Side force at yaw angles (0°, 5°, 10°, 15°, 20°)
- Yaw moment (Nm)
- Pressure distribution visualization
- Comparative ranking across tire/rim combinations

---

## 1. Reference Simulation: TTTR28_22_TSV3

This section documents the AeroCloud simulation used as our validation target.

### Case Information
- **Case Name:** TTTR28_22_TSV3
- **Date:** Wednesday, March 12, 2025
- **Platform:** AeroCloud by NablaFlow (Version 7)
- **Project:** Master Testing

### Geometry
- **Model:** Rolling wheel assembly (appears to be a triathlon/TT wheel)
- **Number of Parts:** 2
  - **Part 1:** TSV3.4 22mm Internal-1 (main wheel body - Rolling part)
  - **Part 2:** TTTR28_22-1 (supporting structure/rim)
- **Model Length:** ~0.65 m (based on force distribution plot)
- **Surface Area:** 0.560 m²

---

## 2. Input Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Quality** | STANDARD | Mesh resolution setting |
| **Ground Setting** | slip | Moving ground (belt simulation) |
| **Fluid** | air | Standard atmospheric conditions |
| **Speed** | 13.9 m/s | ~50 km/h / ~31 mph |
| **Yaw Angle** | 15.0° | Crosswind condition |

### Derived Parameters for OpenFOAM
```
Density (ρ):           1.225 kg/m³
Dynamic Viscosity (μ): 1.81×10⁻⁵ Pa·s
Kinematic Viscosity:   1.48×10⁻⁵ m²/s
Reynolds Number:       ~2.1×10⁵ (turbulent)
```

---

## 3. Results Summary

### Key Metrics - Forces (at 15.0° yaw)

| Force | Symbol | Value | Unit |
|-------|--------|-------|------|
| Drag Force | Fd | 1.31 | N |
| Lift Force | Fl | -8.652×10⁻³ | N |
| Side Force | Fs | 14.10 | N |

### Key Metrics - Coefficients

| Coefficient | Symbol | Value |
|-------------|--------|-------|
| Drag Coefficient | Cd | 0.490 |
| Lift Coefficient | Cl | -3.225×10⁻³ |
| Side Coefficient | Cs | 5.253 |

### Key Metrics - CdA (Coefficient × Area)

| Parameter | Symbol | Value | Unit |
|-----------|--------|-------|------|
| Drag × Area | CdA | 0.011 | m² |
| Lift × Area | ClA | -7.311×10⁻⁵ | m² |
| Side × Area | CsA | 0.119 | m² |

### Key Metrics - Moments

| Moment | Symbol | Value | Unit |
|--------|--------|-------|------|
| Roll Moment | Mr | -4.42 | Nm |
| Pitch Moment | Mp | 0.60 | Nm |
| Yaw Moment | My | 4.34 | Nm |

### Key Metrics - Heat Transfer

| Parameter | Value | Unit |
|-----------|-------|------|
| Total Heat Transfer | 39.316 | W/K |
| Heat Transfer Coefficient | 70.156 | W/m²K |
| Surface Area | 0.560 | m² |

### Parts Breakdown (Drag Force)

| Part Name | Drag Force | Percentage |
|-----------|-----------|------------|
| TSV3.4 22mm Internal-1 | ~0.9 N | ~69% |
| TTTR28_22-1 | ~0.4 N | ~31% |

---

## 4. Visualization Components Explained

### 4.1 Hero Image (3D Preview)
**Description:** Rendered 3D view of the wheel geometry showing streamlines/flow visualization behind the model. The visualization shows the wake structure behind the wheel at 15° yaw angle.

**OpenFOAM Equivalent:**
- Use ParaView for post-processing
- `streamTracer` filter for streamline visualization
- `slice` filter for cross-sectional views

### 4.2 Force Distribution Chart
**Description:** Area-filled line chart showing cumulative drag force along the model's length (X-axis: Position [m], Y-axis: Cumulative Force [N]).

**Available Options:**
- Cumulative Drag / Lift / Side
- Component forces: Drag X/Y/Z, Lift X/Y/Z, Side X/Y/Z

**OpenFOAM Equivalent:**
- Use `forceCoeffs` function object
- Post-process with `forces` utility
- Plot using Python/matplotlib from `postProcessing/forceCoeffs/` data

**Key Observation:** The drag builds up gradually from 0.05m to ~0.35m, then increases more steeply from 0.35m to 0.65m (wheel body contribution).

### 4.3 3D Interactive View
**Description:** WebGL-based 3D viewer allowing rotation, pan, and zoom of the model. Shows pressure distribution or surface results on the geometry.

**OpenFOAM Equivalent:**
- ParaView with VTK/OpenFOAM reader
- Export to STL/OBJ for web viewers (Three.js)

### 4.4 Slices View
**Description:** 2D cross-sectional contour plots of flow field variables at various positions through the domain.

**Configuration Options:**
| Option | Values |
|--------|--------|
| **Field** | Total Pressure Coefficient, Total Pressure Coefficient + LIC, Static Pressure Coefficient, Acoustic Power (Beta) |
| **Direction** | X, Y, Z |
| **Slices Available** | 49 slices total |
| **Color Scale** | -0.60 to 1.00 (Total Pressure Coefficient) |

**OpenFOAM Equivalent:**
- `cuttingPlane` function object
- ParaView slice filter
- Export with `postProcess -func "cutPlaneSurface"`

**Observation:** The pressure coefficient slice shows:
- Blue regions (Cp < 0): Low pressure / acceleration zones
- Red/magenta regions (Cp > 1): Stagnation zones
- Wake structure visible behind the wheel

### 4.5 Parts Breakdown Bar Chart
**Description:** Horizontal bar chart showing contribution of each component to total aerodynamic loads.

**Available Metrics:**
- Drag Force, Lift Force, Side Force
- Roll Moment, Pitch Moment, Yaw Moment
- Heat Transfer, Heat Transfer Coefficient
- Surface Area

**OpenFOAM Equivalent:**
- Use `forceCoeffs` with `patches` specification
- Define multiple `forceCoeffs` function objects for each surface region

---

## 5. Export Options & Model Access

### Available Downloads from AeroCloud

| Export Type | Format | Status | Description |
|------------|--------|--------|-------------|
| **Report** | PDF | Available | Full simulation report with all results |
| **Spreadsheet** | XLSX | Available | Tabular data of all metrics |
| **Slice images** | Images | Expired | Pre-rendered slice visualizations |
| **Raw data** | Unknown | Expired | Full simulation data |

### Model Export for OpenFOAM

**Current Limitations:**
- **No direct STL/OBJ export option visible** from the simulation results page
- The "Raw data" download has **expired** and is no longer available
- The Models Catalog shows **no saved models** for this user

**Recommendations to Obtain Geometry:**
1. **Contact NablaFlow Support** - Request the original geometry files
2. **Re-upload original CAD** - If you have the source geometry, upload to Models Catalog
3. **Check email/original submission** - The model was likely uploaded initially
4. **API Access** - Check if NablaFlow has an API for model retrieval

### Alternative Geometry Solutions

If you cannot obtain the exact geometry:

1. **Parametric Recreation:**
   - Wheel diameter appears to be ~0.65m (based on model length)
   - TSV3 profile suggests specific aero spoke pattern
   - TTTR28_22 suggests 28mm tire width, 22mm rim depth

2. **Open-Source Wheel Models:**
   - OpenFOAM tutorials often include simplified wheel geometries
   - Grab CAD models from GrabCAD or similar

---

## 6. OpenFOAM Setup Guide

### 6.0 Rotation Method Selection

For spoked bicycle wheels, there are three approaches:

| Method | Description | Pros | Cons |
|--------|-------------|------|------|
| **MRF** | Steady-state, source terms only | Fast | Won't capture transient spoke effects |
| **AMI/Sliding Mesh** | Physical rotation with interface interpolation | Captures spoke-wake interaction | Transient, more expensive |
| **Overset/Chimera** | Maximum flexibility | Complex motions | Overkill for pure rotation |

**Recommendation: AMI with pimpleFoam** — Required to capture the unsteady spoke-wake interactions. Research shows an isolated static spoked wheel has **2.2% larger drag** than the same wheel rotating.

### 6.1 Recommended Solver & Settings

This case uses **AMI (Arbitrary Mesh Interface)** for the rotating wheel zone with transient simulation.

| Parameter | Recommendation | Justification |
|-----------|----------------|---------------|
| **Solver** | `pimpleFoam` | Transient, incompressible, PIMPLE algorithm |
| **Turbulence Model** | `kOmegaSST` | Best for external flows with separation |
| **Rotation Method** | AMI sliding mesh | Captures spoke-wake dynamics |
| **Mesh Resolution** | 6-8 million cells | Required for spoked wheel accuracy |
| **Simulation Time** | Several wheel rotations | Allow flow to develop |

```cpp
// system/fvSchemes
ddtSchemes
{
    default         Euler;  // First-order time, or CrankNicolson 0.9 for accuracy
}

divSchemes
{
    default         none;
    div(phi,U)      Gauss linearUpwind grad(U);
    div(phi,k)      Gauss upwind;
    div(phi,omega)  Gauss upwind;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}

gradSchemes
{
    default         Gauss linear;
}

laplacianSchemes
{
    default         Gauss linear corrected;
}

interpolationSchemes
{
    default         linear;
}
```

```cpp
// system/fvSolution
solvers
{
    p
    {
        solver          GAMG;
        smoother        GaussSeidel;
        tolerance       1e-06;
        relTol          0.01;
    }

    pFinal
    {
        $p;
        relTol          0;
    }

    "(U|k|omega)"
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-06;
        relTol          0.1;
    }

    "(U|k|omega)Final"
    {
        $U;
        relTol          0;
    }
}

PIMPLE
{
    nOuterCorrectors    2;
    nCorrectors         2;
    nNonOrthogonalCorrectors 1;
    pRefCell            0;
    pRefValue           0;
}

relaxationFactors
{
    equations
    {
        ".*"            1;
    }
}

### 6.2 Dynamic Mesh Configuration (AMI Rotation)

The wheel rotates using a solidBody motion solver with AMI interface.

```cpp
// constant/dynamicMeshDict
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      dynamicMeshDict;
}

dynamicFvMesh   dynamicMotionSolverFvMesh;

motionSolverLibs ("libfvMotionSolvers.so");

motionSolver    solidBody;

cellZone        rotatingZone;

solidBodyMotionFunction rotatingMotion;

rotatingMotionCoeffs
{
    origin      (0 0 0);      // Wheel center coordinates
    axis        (0 1 0);      // Rotation axis (lateral)
    omega       constant 42.77;  // rad/s = V/R = 13.9/0.325
}
```

**Rotation Speed Calculation:**
```
ω = V / R
ω = 13.9 m/s / 0.325 m = 42.77 rad/s
```

### 6.3 Boundary Conditions

#### Inlet
```cpp
inlet
{
    type            fixedValue;
    // Velocity with 15° yaw angle
    value           uniform (13.43 3.60 0);  // 13.9*cos(15°), 13.9*sin(15°), 0
}
```

#### Outlet
```cpp
outlet
{
    type            inletOutlet;
    inletValue      uniform (0 0 0);
    value           $internalField;
}
```

#### Ground (Moving Belt)
```cpp
ground
{
    type            movingWallVelocity;
    value           uniform (13.43 3.60 0);  // Same as freestream velocity
}
```

**Ground Modeling Note:** Including ground with proper clearance reduces wheel drag coefficient by **1.0-1.8%** compared to no ground. This is essential for realistic results.

#### Wheel Surface (Inside Rotating Zone)
```cpp
wheel
{
    type            movingWallVelocity;  // Wall moves with rotating zone
    value           uniform (0 0 0);
}
```

#### AMI Interface Patches
```cpp
// In constant/polyMesh/boundary, after createPatch
AMI_inner
{
    type            cyclicAMI;
    matchTolerance  0.0001;
    neighbourPatch  AMI_outer;
    transform       noOrdering;
}

AMI_outer
{
    type            cyclicAMI;
    matchTolerance  0.0001;
    neighbourPatch  AMI_inner;
    transform       noOrdering;
}
```

#### Turbulence Inlet Conditions
```cpp
// 0/k
inlet
{
    type            fixedValue;
    value           uniform 0.029;  // k = 1.5*(U*I)^2, I=0.01 (1% turbulence)
}

// 0/omega
inlet
{
    type            fixedValue;
    value           uniform 4.5;    // omega = k^0.5 / (Cmu^0.25 * l), l=0.1*D
}

// 0/nut
inlet
{
    type            calculated;
    value           uniform 0;
}

// AMI patches need special handling
AMI_inner
{
    type            cyclicAMI;
}

AMI_outer
{
    type            cyclicAMI;
}
```

### 6.4 Turbulence Properties

```cpp
// constant/turbulenceProperties
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      turbulenceProperties;
}

simulationType RAS;

RAS
{
    RASModel        kOmegaSST;
    turbulence      on;
    printCoeffs     on;
}
```

### 6.5 Function Objects for Post-Processing
```cpp
// system/controlDict - functions section
functions
{
    forceCoeffs
    {
        type            forceCoeffs;
        libs            (forces);
        writeControl    timeStep;
        writeInterval   100;

        patches         (wheel rim);
        rho             rhoInf;
        rhoInf          1.225;

        CofR            (0 0 0);
        liftDir         (0 0 1);
        dragDir         (0.9659 0.2588 0);  // cos(15°), sin(15°), 0
        pitchAxis       (0 1 0);

        magUInf         13.9;
        lRef            0.65;
        Aref            0.0225;  // Reference area - adjust based on actual frontal area
    }

    // Separate force tracking for each part
    forceCoeffs_wheel
    {
        type            forceCoeffs;
        libs            (forces);
        writeControl    timeStep;
        writeInterval   100;
        patches         (TSV3_wheel);
        // ... same settings as above
    }

    forceCoeffs_rim
    {
        type            forceCoeffs;
        libs            (forces);
        writeControl    timeStep;
        writeInterval   100;
        patches         (TTTR28_rim);
        // ... same settings as above
    }

    // Slice outputs for visualization
    cuttingPlane
    {
        type            surfaces;
        libs            (sampling);
        writeControl    writeTime;

        surfaceFormat   vtk;
        fields          (p U);

        surfaces
        {
            yNormal
            {
                type        cuttingPlane;
                planeType   pointAndNormal;
                pointAndNormalDict
                {
                    point   (0 0 0);
                    normal  (0 1 0);
                }
                interpolate true;
            }
        }
    }
}
```

### 6.5 Mesh Generation with snappyHexMesh

**Target: 6-8 million cells** for accurate spoked wheel results.

#### Geometry Requirements
1. **wheel.stl** - The wheel geometry (tire + rim + spokes)
2. **AMI_cylinder.stl** - Cylindrical surface encompassing the wheel (defines rotating zone boundary)

```cpp
// system/snappyHexMeshDict
castellatedMeshControls
{
    maxLocalCells       1000000;
    maxGlobalCells      8000000;  // Target 6-8M cells
    minRefinementCells  10;
    nCellsBetweenLevels 3;

    features
    (
        {
            file "wheel.eMesh";
            level 3;
        }
        {
            file "AMI_cylinder.eMesh";
            level 2;
        }
    );

    refinementSurfaces
    {
        wheel
        {
            level (3 4);
            patchInfo
            {
                type wall;
            }
        }

        // Critical: AMI zone definition
        AMI_cylinder
        {
            level (2 2);
            faceType boundary;
            cellZone rotatingZone;
            faceZone rotatingZone;
            cellZoneInside inside;
        }
    }

    refinementRegions
    {
        refinementBox
        {
            mode inside;
            levels ((1E15 2));
        }

        wakeRegion
        {
            mode inside;
            levels ((1E15 3));
        }

        // Higher refinement near wheel
        wheelRegion
        {
            mode inside;
            levels ((1E15 4));
        }
    }

    locationInMesh (0.5 0 0);  // Point outside the wheel, inside domain
}

addLayersControls
{
    relativeSizes true;

    layers
    {
        wheel
        {
            nSurfaceLayers 5;
        }
    }

    expansionRatio 1.2;
    finalLayerThickness 0.3;
    minThickness 0.1;
}

meshQualityControls
{
    maxNonOrtho 65;
    maxBoundarySkewness 20;
    maxInternalSkewness 4;
    maxConcave 80;
    minVol 1e-13;
    minTetQuality -1e30;
    minArea -1;
    minTwist 0.02;
    minDeterminant 0.001;
    minFaceWeight 0.05;
    minVolRatio 0.01;
    minTriangleTwist -1;
    nSmoothScale 4;
    errorReduction 0.75;
}
```

#### Post-Mesh: Create AMI Patches
After snappyHexMesh, run createPatch to convert AMI boundaries:

```cpp
// system/createPatchDict
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      createPatchDict;
}

pointSync false;

patches
(
    {
        name AMI_inner;
        patchInfo
        {
            type cyclicAMI;
            matchTolerance 0.0001;
            neighbourPatch AMI_outer;
            transform noOrdering;
        }
        constructFrom patches;
        patches (rotatingZone);
    }
    {
        name AMI_outer;
        patchInfo
        {
            type cyclicAMI;
            matchTolerance 0.0001;
            neighbourPatch AMI_inner;
            transform noOrdering;
        }
        constructFrom patches;
        patches (rotatingZone_slave);
    }
);
```

Run: `createPatch -overwrite`

### 6.6 Simulation Execution Workflow

```bash
# 1. Prepare geometry
surfaceFeatureExtract

# 2. Create background mesh
blockMesh

# 3. Generate snappyHexMesh (parallel recommended for 6-8M cells)
decomposePar
mpirun -np 8 snappyHexMesh -parallel -overwrite
reconstructParMesh -constant

# 4. Create AMI patches
createPatch -overwrite

# 5. Check mesh quality
checkMesh

# 6. Initialize fields
setFields  # If needed for initial conditions

# 7. Run simulation (allow several wheel rotations)
decomposePar
mpirun -np 8 pimpleFoam -parallel

# 8. Reconstruct and post-process
reconstructPar
postProcess -func forceCoeffs
```

**Simulation Time Estimation:**
- Wheel circumference: 2πR = 2π × 0.325 = 2.04 m
- Time per rotation: C/V = 2.04/13.9 = 0.147 s
- Recommend: 5-10 rotations = 0.74 - 1.47 s simulation time
- Timestep: Δt ≈ 1e-4 to 1e-5 s (based on CFL < 1)

### 6.7 Spoke Modeling Options

| Approach | Description | Cell Count | Accuracy |
|----------|-------------|------------|----------|
| **Fully Resolved** | Mesh actual spoke geometry | 6-8M+ | Highest |
| **Blade Element Method** | Model spokes as virtual disks | 2-4M | Good for many thin spokes |
| **Simplified** | Disk wheel approximation | 1-2M | Quick estimates only |

**Recommendation:** Use fully resolved spoke geometry for tire/rim optimization studies where leading edge effects matter.

### 6.8 Ground Modeling Considerations

| Configuration | Effect on Cd | Notes |
|---------------|--------------|-------|
| No ground | Baseline | Unrealistic |
| Ground with clearance | -1.0 to -1.8% | Recommended |
| Ground contact patch | Most realistic | Complex mesh |

**Implementation Options:**
1. **Fixed clearance:** Small gap (1-2mm) between tire and ground
2. **Step contact:** Simplified contact representation
3. **Moving belt:** Ground moves at freestream velocity (essential)

### 6.9 Slice Visualization in ParaView

To replicate AeroCloud's slice visualization:
```python
# ParaView Python script
from paraview.simple import *

# Load OpenFOAM case
foam = OpenFOAMReader(FileName='case.foam')

# Create slice
slice1 = Slice(Input=foam)
slice1.SliceType = 'Plane'
slice1.SliceType.Origin = [0.0, 0.0, 0.0]
slice1.SliceType.Normal = [1, 0, 0]  # X-normal slice

# Color by pressure coefficient
ColorBy(slice1, ('POINTS', 'p'))

# Set color range (-0.6 to 1.0 for Cp)
# Note: Convert kinematic pressure to Cp using:
# Cp = p / (0.5 * rhoInf * U^2)
```

---

## 7. OpenFOAM MCP Server Integration

The OpenFOAM MCP Server provides AI-powered tools to assist with this simulation workflow.

### 7.1 Available MCP Tools for This Case

| Tool | Purpose | Application to TTTR28_22_TSV3 |
|------|---------|-------------------------------|
| `start_cfd_assistance` | Begin intelligent CFD conversation | Get guidance on case setup |
| `analyze_stl_geometry` | STL preprocessing analysis | Check wheel geometry for snappyHexMesh readiness |
| `assess_mesh_quality` | Mesh quality evaluation | Validate mesh before solving |
| `analyze_turbulent_flow` | Turbulent flow analysis | Get k-omega SST parameters and y+ recommendations |
| `execute_openfoam_operation` | Run OpenFOAM commands | Execute blockMesh, snappyHexMesh, simpleFoam |
| `analyze_cfd_results` | Result interpretation | Analyze force coefficients and flow patterns |

### 7.2 Recommended MCP Workflow

```
1. Geometry Preparation
   └─> analyze_stl_geometry(wheel.stl)
       - Check watertightness
       - Validate normals
       - Get feature edge extraction guidance

2. Flow Analysis Setup
   └─> analyze_turbulent_flow({
         velocity: 13.9,
         characteristic_length: 0.65,
         fluid: "air"
       })
       - Get Reynolds number confirmation
       - Receive k-omega SST inlet conditions
       - Get y+ target and first cell height

3. Mesh Quality Check
   └─> assess_mesh_quality(case_path)
       - Non-orthogonality assessment
       - Skewness evaluation
       - Solver compatibility check

4. Simulation Execution
   └─> execute_openfoam_operation({
         operation: "solve",
         solver: "simpleFoam"
       })

5. Results Analysis
   └─> analyze_cfd_results(case_path)
       - Force coefficient extraction
       - Comparison with AeroCloud targets
       - Flow pattern interpretation
```

### 7.3 MCP Server Configuration

The MCP server is configured in `~/.claude/mcp.json`:
```json
{
  "mcpServers": {
    "openfoam": {
      "command": "/home/constantine/repo/openfoam-mcp-server/build/openfoam-mcp-server-test",
      "args": [],
      "env": {
        "LD_LIBRARY_PATH": "/opt/openfoam13/platforms/linux64GccDPInt32Opt/lib/dummy:/opt/openfoam13/platforms/linux64GccDPInt32Opt/lib",
        "FOAM_INST_DIR": "/opt/openfoam13",
        "WM_PROJECT_DIR": "/opt/openfoam13",
        "FOAM_LIBBIN": "/opt/openfoam13/platforms/linux64GccDPInt32Opt/lib",
        "FOAM_APPBIN": "/opt/openfoam13/platforms/linux64GccDPInt32Opt/bin",
        "FOAM_ETC": "/opt/openfoam13/etc",
        "PATH": "/opt/openfoam13/platforms/linux64GccDPInt32Opt/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
      }
    }
  }
}
```

### 7.4 Socratic Learning Integration

The MCP server uses educational questioning to guide understanding:

```
User: "Set up the wheel simulation at 15° yaw"

MCP Response with Socratic Questions:
- CLARIFY: "What specific aerodynamic metrics are you targeting - drag, side force, or yaw stability?"
- EXPLORE: "At 15° yaw, side forces become significant. How do you expect the pressure distribution to differ from 0° yaw?"
- CONFIRM: "The Reynolds number of 2.1×10⁵ indicates turbulent flow. Should we use wall functions or resolve the boundary layer?"
- APPLY: "Given the rotating wheel, how should we handle the contact patch between wheel and ground?"
```

---

## 8. Solver Selection Reference

### Quick Reference: External Flow Solvers

| Scenario | Solver | Turbulence | Notes |
|----------|--------|------------|-------|
| Wheel aerodynamics (steady) | `simpleFoam` | kOmegaSST | This case |
| Wheel aerodynamics (unsteady) | `pimpleFoam` | kOmegaSST | For vortex shedding |
| With ground heating | `buoyantSimpleFoam` | kOmegaSST | If thermal effects matter |
| High-speed (>100 m/s) | `rhoSimpleFoam` | kOmegaSST | Compressibility effects |

### Turbulence Model Comparison

| Model | Best For | Accuracy | Cost |
|-------|----------|----------|------|
| **kOmegaSST** | Separated flows, adverse pressure gradients | High | Medium |
| kEpsilon | Fully turbulent internal flows | Medium | Low |
| SpalartAllmaras | Attached boundary layers | Medium | Low |
| LES | Unsteady wakes, acoustics | Very High | Very High |

**Recommendation for TTTR28_22_TSV3:** Use `kOmegaSST` - optimal for the separated flow regions behind the wheel spokes and the complex wake structure at yaw.

---

## 9. Validation Targets

Use these values to validate your OpenFOAM simulation:

| Metric | Target | Tolerance | Priority |
|--------|--------|-----------|----------|
| Drag Force (Fd) | 1.31 N | ±5% | High |
| Side Force (Fs) | 14.10 N | ±5% | High |
| Drag Coefficient (Cd) | 0.490 | ±5% | High |
| Side Coefficient (Cs) | 5.253 | ±5% | High |
| Yaw Moment (My) | 4.34 Nm | ±10% | Medium |
| Lift Force (Fl) | -8.652×10⁻³ N | ±20% | Low |

### Mesh Independence Study

Run at least 3 mesh levels to ensure mesh independence:

| Mesh Level | Cell Count | Expected Cd | Notes |
|------------|------------|-------------|-------|
| Coarse | ~500k | May vary 10%+ | Quick validation |
| Medium | ~1.5M | Within 5% | Design level |
| Fine | ~4M | Reference | Validation level |

---

## 10. Complete Case Directory Structure

```
TTTR28_22_TSV3/
├── 0/
│   ├── U
│   ├── p
│   ├── k
│   ├── omega
│   └── nut
├── constant/
│   ├── transportProperties
│   ├── turbulenceProperties
│   └── triSurface/
│       ├── wheel.stl
│       └── rim.stl
├── system/
│   ├── controlDict
│   ├── fvSchemes
│   ├── fvSolution
│   ├── blockMeshDict
│   ├── snappyHexMeshDict
│   ├── surfaceFeatureExtractDict
│   └── decomposeParDict
└── postProcessing/
    └── forceCoeffs/
        └── 0/
            └── coefficient.dat
```

---

## 11. Summary

### What You Can Extract from AeroCloud:
- Simulation parameters (speed, yaw, fluid properties)
- Force and moment results
- Coefficient data
- PDF report and XLSX spreadsheet
- Color scale ranges for visualization

### What You Need Externally:
- Geometry file (STL/OBJ) - Not directly downloadable
- Raw simulation data - Expired
- Mesh settings details - Not visible

### Recommended Next Steps:
1. Download the Report (PDF) and Spreadsheet (XLSX) while available
2. Contact NablaFlow to request geometry files
3. Set up OpenFOAM case with parameters from this summary
4. Use OpenFOAM MCP Server tools for guided setup and validation
5. Use validation targets for mesh independence study

---

## 12. References

- **OpenFOAM Foundation**: [https://openfoam.org/](https://openfoam.org/)
- **OpenFOAM MCP Server**: [https://github.com/webworn/openfoam-mcp-server](https://github.com/webworn/openfoam-mcp-server)
- **Model Context Protocol**: [https://modelcontextprotocol.io/](https://modelcontextprotocol.io/)
- **CFD Theory**: "An Introduction to Computational Fluid Dynamics" by Versteeg & Malalasekera
- **Turbulence Modeling**: "Turbulence Modeling for CFD" by Wilcox

---

*Generated for OpenFOAM reproduction of AeroCloud simulation TTTR28_22_TSV3*
