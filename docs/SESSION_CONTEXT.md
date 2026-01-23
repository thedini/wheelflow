# Session Context - OpenFOAM Analysis
**Last Updated**: $(date)

## Current Task
Exploring and analyzing OpenFOAM wheelflow cases using MCP tools

## Key Directories
- Working dir: /home/constantine/repo/openFOAM
- Cases location: /home/constantine/repo/openFOAM/wheelflow/cases/
- MCP server: /home/constantine/repo/openfoam-mcp-server/build/openfoam-mcp-server-test

## Cases Found
- 65f9dec5 - has mesh and postProcessing results
- (need to list others)

## Progress
- [x] Located OpenFOAM cases
- [ ] Assess mesh quality for 65f9dec5
- [ ] Analyze CFD results
- [ ] Review other cases

## Last Action
Attempted MCP tool call for assess_mesh_quality - checking result
Thu Jan 22 07:58:01 PM EST 2026

## 65f9dec5 Mesh Quality (checkMesh)
- **Cells**: 8,126,722
- **Points**: 8,420,192
- **Cell types**: 97.5% hexahedra, 2.4% polyhedra
- **Max aspect ratio**: 17.64 (OK)
- **Max non-orthogonality**: 64.98° (avg 4.2°) - OK
- **Max skewness**: 4.81 - **1 highly skewed face** (warning)
- **Domain**: (-2,-1.5,0) to (5,1.5,2) = 7x3x2 m
- **Patches**: inlet, outlet, ground, top, sides, wheel

## Status
Mesh check passed with 1 warning (skewness)

## 65f9dec5 Simulation Results
**STATUS: DIVERGED**
- Force coefficients exploded from ~10^8 at iteration 80 to 10^38 at iteration 98
- Simulation became numerically unstable
- Need to check: relaxation factors, time step, boundary conditions

## 65f9dec5 Case Analysis

### Setup
- **Solver**: simpleFoam (steady-state SIMPLE)
- **Turbulence**: k-omega 
- **Inlet velocity**: 13.9 m/s (~50 km/h)
- **Ground**: Moving wall at 13.9 m/s (rolling road)
- **Wheel**: Stationary (U=0,0,0) - **ISSUE: should rotate!**

### Potential Divergence Cause
The wheel BC is U=(0,0,0) while ground is U=(13.9,0,0).
At the wheel-ground contact region, this creates a 13.9 m/s velocity discontinuity.
This can cause extreme gradients and numerical instability.

### Recommendation
For a rolling wheel, use rotating boundary condition (MRF or rotating wall)
so wheel surface velocity matches ground at contact patch.

---
=== All 18 Cases Status ===

| Case     | Status      | Iterations | Cd           |
|----------|-------------|------------|--------------|
| 18d67781 | CONVERGED   | 500        | 0.075        |
| 30a39dde | CONVERGED?  | 500        | 0 (suspect)  |
| 632ae3eb | NOT RUN     | -          | -            |
| 65f9dec5 | DIVERGED    | 98         | 10^38        |
| 66dff05e | NOT RUN     | -          | -            |
| 79f5ae3c | DIVERGED    | 98         | 10^38        |
| 8d6ed970 | NOT RUN     | -          | -            |
| 8f3f618c | NOT RUN     | -          | -            |
| b193bf67 | CONVERGED   | 500        | 0.050        |
| b725da61 | NOT RUN     | -          | -            |
| c03294bd | NOT RUN     | -          | -            |
| c80e764a | NOT RUN     | -          | -            |
| ca5cdb0b | NOT RUN     | -          | -            |
| d7ff69f3 | CONVERGED?  | 500        | 0 (suspect)  |
| e4c729d4 | NOT RUN     | -          | -            |
| fdc32e67 | CONVERGED   | 500        | 0.075        |
| gpu_test | UNSTABLE    | 6          | -20          |

## Summary
- 3 converged well: 18d67781, b193bf67, fdc32e67
- 2 converged but Cd=0: 30a39dde, d7ff69f3 (check setup)
- 2 diverged: 65f9dec5, 79f5ae3c  
- 9 not run yet
- 1 GPU test unstable

## Key Finding: Mesh Size vs Stability

| Case     | Cells    | Max Skew | Status     |
|----------|----------|----------|------------|
| 18d67781 | 60,804   | 2.08     | CONVERGED  |
| 65f9dec5 | 8,126,722| 4.81     | DIVERGED   |

Same solver settings, same BCs - difference is mesh.
Fine mesh (8M cells) with higher skewness diverged.

## Recommendations for Diverged Cases
1. Use `nNonOrthogonalCorrectors 1` or `2` for high-skew mesh
2. Use more diffusive schemes: `upwind` instead of `linearUpwind`
3. Lower relaxation factors: U=0.5, p=0.2
4. Or: improve mesh quality (reduce skewness < 3)

---
Last updated: $(date)
Thu Jan 22 08:06:08 PM EST 2026

## Converged Case 18d67781 Results
- Cd = 0.151 (drag coeff, Aref=0.1 m²)
- Cl = 0.009 (lift coeff)
- Cm = 0.075 (moment coeff)
- Converged smoothly over 500 iterations
- Reference velocity: 13.9 m/s

## Next Steps
1. Run remaining cases on coarse mesh first
2. Fix diverged cases by lowering relaxation or improving mesh
3. Consider adding rotating wall BC for wheel
4. Compare different mesh resolutions

---

---
## New Simulation Run
**Time**: $(date)
**Job ID**: cdebe65a
**Quality**: pro (better stability)
**Wheel radius**: 0.342m (detected from STL)
**Speed**: 13.9 m/s

### Wheelflow Service
- Started as systemd user service
- Running on port 8000
- Auto-restart enabled
Thu Jan 22 08:11:02 PM EST 2026

---
## Issue Found: STL Scaling Bug

**Problem**: app.py hardcodes `scale=0.001` (mm to m) but uploaded STL was already in meters.
**Result**: Wheel became 0.68mm instead of 0.68m, too small for domain, patch removed.

**Location**: `/home/constantine/repo/openFOAM/wheelflow/backend/app.py` line 359-364

**Fix needed**: Use the `suggested_scale` from validation instead of hardcoded 0.001
```python
# Current (wrong):
transform_info = transform_stl_for_openfoam(src, dst, scale=0.001, ...)

# Should be:
validation = validate_stl_file(src)
transform = get_stl_transform_for_openfoam(validation.geometry)
transform_info = transform_stl_for_openfoam(src, dst, scale=transform["scale"], ...)
```

---
## Fixes Applied
1. **STL scaling** - Now auto-detects units and uses suggested_scale
2. **foamRun** - Updated from simpleFoam to foamRun -solver incompressibleFluid
3. **Systemd service** - Added all OpenFOAM environment variables

**New Job**: 8df94ff9
Thu Jan 22 08:24:14 PM EST 2026

## Simulation 8df94ff9 - SUCCESS!
**Status**: COMPLETE
**Results**:
- Cd = 0.144
- Cl = 0.078  
- CdA = 0.0144 m²
- Drag = 1.71 N at 13.9 m/s
- Lift = 0.93 N

All fixes working. Now adding user-friendly scale warnings.

---
## All Tasks Complete

### Summary of Changes
1. **Wheelflow systemd service** - Created at `~/.config/systemd/user/wheelflow.service`
   - Auto-restart enabled
   - All OpenFOAM env vars configured
   - Running on port 8000

2. **Fixed STL scaling bug** (app.py:357-374)
   - Now auto-detects units (mm vs m)
   - Uses suggested_scale from validation

3. **Fixed foamRun command** (app.py:426-429)
   - Changed from `simpleFoam` to `foamRun -solver incompressibleFluid`
   - Updated reconstruction logic

4. **Added user-friendly scale warnings** (app.py:170-191)
   - Shows scale_message on upload
   - Warns if dimensions unusual for bicycle wheel

### Service Commands
```bash
# Start/stop/restart
systemctl --user start wheelflow
systemctl --user stop wheelflow  
systemctl --user restart wheelflow

# Check status/logs
systemctl --user status wheelflow
journalctl --user -u wheelflow -f
```

### Successful Test Run
- Job ID: 8df94ff9
- Cd = 0.144, Cl = 0.078
- Drag = 1.71 N at 13.9 m/s
Thu Jan 22 08:28:20 PM EST 2026
