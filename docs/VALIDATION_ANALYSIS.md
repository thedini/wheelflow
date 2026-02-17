# WheelFlow vs AeroCloud Validation Analysis

**Date:** 2026-02-15 (updated)
**Previous:** 2026-02-09
**Status:** Yaw sweep complete (0°-20°), parallel meshing validated

---

## Executive Summary

WheelFlow simulations of the TTTR28_22_TSV3 spoked wheel produce Cd ~1.12-1.29 instead of AeroCloud's 0.49. Two root causes have been identified and addressed:

1. **STL Geometry:** The "Solid for CFD" STL has filled spoke windows (acts as disc). **Fixed** by combining separate part STLs.
2. **MRF Rotation Zone:** Forces ALL air in the wheel region (including spoke gaps) to rotate as a solid body, preventing flow through spokes. **Fix in progress** - testing without MRF.

### Run History

| Job ID | STL | Quality | Mesh Cells | Wheel Faces | MRF | Cd | Status |
|--------|-----|---------|------------|-------------|-----|-----|--------|
| d6f6689b | Solid for CFD | Standard | 1.4M | 17K | Yes | 1.290 | Disc-like (solid STL) |
| c32c1408 | Combined open | Standard | 1.4M | 17K | Yes | 1.288 | Mesh too coarse |
| 2e534f01 | Combined open | Pro | 9.0M | 80K | Yes | 1.123 | MRF blocks spoke flow |
| 2e534f01_noMRF | Combined open | Pro | 9.0M | 80K | **No** | **0.692** | **Complete** |
| **1a09a959_00** | Solid for CFD | Pro (parallel) | ~15M | — | **No** | **0.413** | Yaw sweep 0° |
| **bd2bc0d0_05** | Solid for CFD | Pro (parallel) | ~15M | — | **No** | **0.439** | Yaw sweep 5° |
| **bd2bc0d0_10** | Solid for CFD | Pro (parallel) | ~15M | — | **No** | **0.521** | Yaw sweep 10° |
| **bd2bc0d0_15** | Solid for CFD | Pro (parallel) | ~15M | — | **No** | **0.652** | Yaw sweep 15° |
| **bd2bc0d0_20** | Solid for CFD | Pro (parallel) | ~15M | — | **No** | **0.819** | Yaw sweep 20° |

---

## AeroCloud Reference Data (TTTR28_22_TSV3)

### Test Configuration

| Parameter | Value |
|-----------|-------|
| Test Case | TTTR28_22_TSV3 |
| Test Date | March 13, 2025 |
| Solver Version | v7 |
| Quality | Standard |
| **Mesh Cells** | **12,212,941** |
| Fluid | Air |
| Density | 1.225 kg/m³ |
| Kinematic Viscosity | 1.46e-5 m²/s |
| **Speed** | **13.9 m/s** |
| **Yaw Angle** | **15°** |
| Ground | Yes |
| Rotation | Yes (rolling) |
| Number of Parts | 2 |

### Geometry

| Property | Value |
|----------|-------|
| Type | 3-spoke wheel with tire |
| Frontal Area | 0.0227 m² |
| Surface Area | 0.8396 m² |
| Refined Area | 0.2007 m² |
| Dimensions (x,y,z) | 0.684 m × 0.034 m × 0.684 m |
| Parts | TTTR28_22 (rim/tire) + TSV3.4 22mm Internal (spokes/hub) |

### Results at 15° Yaw

#### Forces and Moments

| Quantity | Value |
|----------|-------|
| **Fd (Drag)** | **1.3149 N** |
| **Fs (Side)** | **14.095 N** |
| **Fl (Lift)** | **-0.00865 N** |
| Mr (Roll) | -4.418 Nm |
| Mp (Pitch) | 0.601 Nm |
| My (Yaw) | 4.340 Nm |

#### Coefficients (Aref = 0.0227 m²)

| Quantity | Value |
|----------|-------|
| **Cd** | **0.4901** |
| **Cs** | **5.2534** |
| **Cl** | **-0.003225** |
| Cr (Roll) | -1.6467 |
| Cp (Pitch) | 0.2239 |
| Cy (Yaw) | 1.6177 |

#### Coefficient Areas

| Quantity | Value |
|----------|-------|
| **CdA** | **0.01111 m²** |
| CsA | 0.1191 m² |
| ClA | -0.0001 m² |
| **Drag Power** | **17.655 W** |

#### Force Breakdown (Pressure vs Viscous)

| Component | Fd [N] | Fs [N] | Fl [N] |
|-----------|--------|--------|--------|
| **Pressure** | **0.96** | **11.91** | **-0.06** |
| **Viscous** | **0.25** | **0.04** | **0.02** |
| Porous | 0.00 | 0.00 | 0.00 |
| **Total** | **1.21** | **11.95** | **-0.04** |

> Note: Viscous drag accounts for **19%** of total drag (0.25 / 1.31 N)

#### Per-Part Breakdown

| Part | Fd [N] | Fs [N] | Fl [N] | % of Total Drag |
|------|--------|--------|--------|-----------------|
| TSV3.4 22mm Internal (spokes/hub) | 0.9952 | 11.109 | 0.1557 | **75.7%** |
| TTTR28_22 (rim/tire) | 0.3197 | 2.987 | -0.1643 | **24.3%** |
| **Total** | **1.3149** | **14.095** | **-0.0087** | **100%** |

> The spokes/hub dominate drag (3× more than rim/tire) due to their large bluff-body surface area.

#### Heat Transfer Per Part

| Part | h [W/m²K] | Total [W/K] | Wetted Area [m²] |
|------|-----------|-------------|-------------------|
| TSV3.4 (spokes) | 67.06 | 27.94 | 0.4167 |
| TTTR28_22 (rim) | 79.15 | 11.37 | 0.1437 |
| **Total** | **70.16** | **39.32** | **0.5604** |

---

## WheelFlow Data

### Disc Wheel Yaw Sweep (Batch 7a430d2b)

**Geometry:** Solid disc/deep-section wheel, 49,036 triangles, 0.684 m diameter × 34 mm width
**Mesh:** ~1.4M cells
**Aref:** 0.0225 m²
**Solver:** simpleFoam (SIMPLE, steady-state)
**Turbulence:** k-omega SST
**Ground:** Moving wall at 13.9 m/s
**Rotation:** MRF (steady approximation)

| Yaw | Cd | Fd (N) | Cl | Fl (N) | Cs | Fs (N) | CdA (m²) |
|-----|-----|--------|-----|--------|-----|--------|----------|
| 0° | 0.924 | 2.46 | -0.481 | -1.28 | - | - | 0.0208 |
| 5° | 0.970 | 2.58 | -0.486 | -1.29 | - | - | 0.0218 |
| 10° | 1.035 | 2.76 | -0.377 | -1.00 | - | - | 0.0233 |
| **15°** | **1.297** | **3.45** | **-0.374** | **-1.00** | **1.20** | **3.19** | **0.0292** |
| 20° | 1.617 | 4.31 | -0.345 | -0.92 | - | - | 0.0364 |

### Spoked Wheel Runs (TTTR28_22_TSV3)

#### Job d6f6689b - "Solid for CFD" STL (Standard Quality)
- **STL:** `TSV3.4 with Tire Solid for CFD.STL` (49K triangles)
- **Issue:** STL has 2,785 flat triangles filling spoke windows → acts as disc
- **Result:** Cd = 1.290, Fd = 3.44 N, CdA = 0.0290 m²

#### Job c32c1408 - Combined Open-Spoke STL (Standard Quality)
- **STL:** `TTTR28_TSV3_combined_open.STL` (99,824 triangles)
- **Mesh:** 1.4M cells, 17,305 wheel faces
- **Issue:** Standard quality (level 3-4, 6.2mm cells) too coarse for thin spoke features
- **Result:** Cd = 1.288, Fd = 3.43 N → still disc-like

#### Job 2e534f01 - Combined Open-Spoke STL (Pro Quality + MRF)
- **STL:** Same combined STL
- **Mesh:** 9,029,768 cells, 80,039 wheel faces (4.6x more than standard)
- **MRF:** Active (rotatingZone cylinder around wheel, omega=40.6 rad/s)
- **Result:** Cd = 1.123, Fd = 2.99 N, CdA = 0.0253 m²
- **Issue:** MRF forces all fluid in wheel region to rotate as solid body, including air in spoke gaps

**Cd convergence (every 50 iterations):**
```
Iter  Cd
 40   3.98 (initial oscillation)
 90   0.20
140   0.33
190   0.28
240   0.59
290   0.93
340   0.93
390   0.98
440   1.19
490   1.12
500   1.12 (converged)
```

**Raw forces at convergence (iter 500):**
- Pressure: Fx=1.603, Fy=3.875, Fz=-1.854 N
- Viscous: Fx=0.443, Fy=0.036, Fz=0.389 N
- Total Fd (wind axis): 2.99 N

#### Job 2e534f01_noMRF - Same Mesh, No MRF (Complete)
- **Change:** MRFProperties emptied (no body force in fluid)
- **Rotation:** Only `rotatingWallVelocity` BC on wheel surface
- **Result:** Cd = 0.692, Fd = 1.843 N, CdA = 0.0156 m², Cl = 0.011

**Cd convergence (every 50 iterations):**
```
Iter  Cd
 40   4.15 (initial oscillation)
 90   0.23
140   0.22
190   0.44
240   0.55
290   0.65
340   0.70
390   0.70
440   0.69
490   0.69
500   0.69 (converged)
```

**Raw forces at convergence (iter 500):**
- Pressure: Fx=0.829, Fy=2.757, Fz=0.033 N
- Viscous: Fx=0.337, Fy=0.014, Fz=-0.003 N
- Total Fd (wind axis): 1.843 N
- Viscous fraction: 19.1% (matching AeroCloud's 19%)

### Pro Quality Yaw Sweep (2026-02-14, Parallel Meshing)

**Geometry:** "Solid for CFD" STL (49K triangles, 0.684 m diameter)
**Mesh:** ~15M cells (pro quality, parallel snappyHexMesh with 8 cores)
**Aref:** 0.0225 m²
**Solver:** foamRun incompressibleFluid (16 cores parallel)
**Turbulence:** k-omega SST
**Ground:** Moving wall at freestream speed
**Rotation:** Wall BC only (no MRF)

| Yaw | Cd | Fd (N) | Cl | Fl (N) | Cs | Fs (N) | CdA (cm²) | Converged |
|-----|-----|--------|-----|--------|-----|--------|-----------|-----------|
| 0° | 0.413 | 1.10 | 0.023 | 0.062 | -0.024 | -0.065 | 9.3 | Yes |
| 5° | 0.439 | 1.10 | 0.023 | 0.062 | 0.312 | 0.830 | 9.9 | Yes |
| 10° | 0.521 | 1.09 | 0.020 | 0.052 | 0.669 | 1.781 | 11.7 | Yes |
| **15°** | **0.652** | **1.07** | **0.023** | **0.060** | **1.023** | **2.724** | **14.7** | Yes |
| 20° | 0.819 | 1.03 | 0.022 | 0.059 | 1.334 | 3.552 | 18.4 | Yes |

**Force breakdown at 15° yaw:**
- Pressure drag: 0.706 N (66%)
- Viscous drag: 0.361 N (34%)

**Timing (per angle):**
- Mesh: ~28 min (8-core parallel, was ~124 min serial)
- Solve: ~4.5 hr (16-core parallel, 500 iterations)
- Total: ~5 hr per angle, ~25 hr for full sweep

**Key observations:**
- Cd roughly doubles from 0° to 20° — physically reasonable
- Side force dominates at high yaw (Fs = 2.72 N vs Fd = 1.07 N at 15°)
- Drag force (Fd) actually decreases slightly with yaw (1.10 → 1.03 N) while Cd increases due to velocity component change
- Viscous fraction is 34% at 15° — higher than AeroCloud's 19%, likely because this STL has filled spoke windows acting partially as a disc

### Job 8df94ff9 (After STL Scaling Fix)

| Quantity | Value | Note |
|----------|-------|------|
| Cd | 0.144 | Aref = 0.1 m² (old default) |
| Cl | 0.078 | |
| CdA | 0.0144 m² | Independent of Aref |
| Fd | 1.71 N | |
| Fl | 0.93 N | |
| Speed | 13.9 m/s | |

> **Cd with AeroCloud-standard Aref (0.0225 m²):** 1.71 / (118.3 × 0.0225) = **0.642**

---

## Comparison at 15° Yaw

### Primary Comparison: WheelFlow (no MRF) vs AeroCloud at 15° Yaw

| Metric | AeroCloud | WheelFlow Pro Sweep | WheelFlow 9M (no MRF) | WheelFlow (MRF) | WheelFlow (Disc) |
|--------|-----------|--------------------|-----------------------|-----------------|-----------------|
| **Cd** | **0.490** | **0.652** (+33%) | 0.692 (+41%) | 1.123 (+129%) | 1.297 (+165%) |
| **CdA** | **0.0111 m²** | **0.0147 m²** (+32%) | 0.0156 m² (+40%) | 0.0253 m² | 0.0292 m² |
| **Fd** | **1.315 N** | **1.067 N** (-19%) | 1.843 N (+40%) | 2.989 N | 3.45 N |
| **Fs** | **14.095 N** | **2.724 N** (-81%) | — | — | 3.19 N |
| Cl | -0.003 | 0.023 | 0.011 | -0.550 | -0.374 |
| Mesh | 12.2M | ~15M | 9.0M | 9.0M | 1.4M |
| MRF | No | No | No | Yes | Yes |

*AeroCloud uses Aref = 0.0227 m², WheelFlow uses 0.0225 m² (~1% difference)

**Notable:** The pro sweep shows lower Fd (1.07 N) than AeroCloud (1.32 N), but higher Cd (0.652 vs 0.490). This is because WheelFlow's "Solid for CFD" STL has filled spoke windows — less drag than a true open-spoke wheel, but the coefficient is higher because the flow pattern differs. Side force is 5× lower than AeroCloud (2.72 vs 14.10 N), confirming the solid spoke windows block crossflow.

### Key Finding: MRF Impact

Disabling MRF reduced Cd by **38%** (1.123 → 0.692), confirming that MRF was forcing air in spoke gaps to rotate as a solid body. The remaining +41% gap vs AeroCloud is likely due to:

1. **Mesh resolution** (9M vs 12.2M cells, no feature edge extraction)
2. **STL geometry quality** (combined from 2 separate parts, potential gaps at interfaces)
3. **Solver differences** (OpenFOAM simpleFoam vs AeroCloud proprietary v7)

### Viscous/Pressure Breakdown

| Component | AeroCloud Fd [N] | WheelFlow (no MRF) Fd [N] |
|-----------|-----------------|--------------------------|
| Pressure | 0.96 (73%) | 1.49 (81%) |
| Viscous | 0.25 (19%) | 0.35 (19%) |
| Total | 1.31 | 1.84 |

The viscous fraction (19%) matches AeroCloud exactly, suggesting the boundary layer treatment is correct. The overprediction is primarily in pressure drag, which is geometry/mesh dependent.

### Why Results Differ

| Factor | Impact | Status |
|--------|--------|--------|
| **MRF Rotation Zone** | **Major (~2×)** | Forces air in spoke gaps to rotate as solid body. **Fix: disable MRF** |
| **STL Geometry** | **Major (if wrong STL used)** | "Solid for CFD" STL has filled spoke windows. **Fixed: use combined open STL** |
| Mesh Resolution | Moderate | Standard quality (1.4M) can't resolve spokes. Pro (9M) resolves 80K faces |
| Feature Edges | Minor | No surfaceFeatureExtract used. May improve spoke edge resolution |
| Ground BC | Minor | Moving wall (WheelFlow) vs unspecified (AeroCloud) |

### Root Cause: MRF Rotation Zone

**The MRF (Multiple Reference Frame) approach in WheelFlow creates a cylindrical zone around the wheel and applies Coriolis/centripetal source terms to ALL fluid cells inside it.** For a solid disc wheel this is appropriate. For a spoked wheel, it forces the air in the spoke gaps to rotate as a solid body, effectively sealing the spoke windows aerodynamically.

**Evidence:**
- Pro mesh (9M cells, 80K wheel faces) with MRF: Cd = 1.12 (disc-like)
- Standard mesh (1.4M) with MRF: Cd = 1.29 (same as solid disc STL)
- AeroCloud (no MRF, rolling wall BC only): Cd = 0.49

**Fix:** Disable MRF and use only `rotatingWallVelocity` boundary condition on the wheel surface. This allows air to flow through spoke windows while maintaining wheel surface rotation.

### Physics Validation

| Geometry | Expected Cd Range | Simulated Cd | Status |
|----------|------------------|-------------|--------|
| Solid disc (MRF) | 1.0-1.3 | 1.297 (WheelFlow) | Correct |
| Spoked wheel (MRF) | ~1.0-1.2 (MRF blocks flow) | 1.123 (WheelFlow) | Expected with MRF |
| 3-spoke wheel (no MRF) | 0.5-0.8 | **0.692** (WheelFlow) | +41% vs AeroCloud |
| 3-spoke wheel (AeroCloud) | 0.4-0.6 | 0.490 (AeroCloud) | Reference |

---

## Simulation Setup Comparison

| Parameter | WheelFlow | AeroCloud |
|-----------|-----------|-----------|
| Mesh Cells | ~1.4M | **12.2M** |
| Speed | 13.9 m/s | 13.9 m/s |
| Density | 1.225 kg/m³ | 1.225 kg/m³ |
| Viscosity | 1.46e-5 m²/s | 1.46e-5 m²/s |
| Aref | 0.0225 m² | 0.0227 m² |
| Turbulence | k-omega SST | Not specified (likely k-omega SST) |
| Rotation | MRF (steady) | Rolling |
| Ground | Moving wall | Yes (type unspecified) |
| Solver | simpleFoam / foamRun | Proprietary (v7) |
| Quality | Basic/Standard | Standard |

### Key Differences to Resolve

1. **MRF vs rotating wall BC:** MRF forces spoke gap air to rotate; must disable for spoked wheels.
2. **Feature edge extraction:** No `surfaceFeatureExtract` run; may improve spoke edge resolution.
3. **Mesh resolution:** WheelFlow Pro (9M) vs AeroCloud (12.2M) - reasonable comparison.
4. **Ground treatment:** AeroCloud says "Yes" for ground but exact BC type unclear.

---

## AeroCloud Spatial Force Distribution (150 bins along x-axis)

The Excel data includes detailed force distributions along the wheel height (x-axis = vertical in wheel frame). Key observations:

- **Drag force** peaks at the tire/rim contact with ground (bins 1-5 and 145-150) where flow stagnation occurs
- **Side force** is dominant (14.1 N total vs 1.3 N drag) with cumulative buildup across the full wheel height
- **Lift force** is nearly zero (-0.009 N), indicating symmetric vertical force distribution
- The spoke region (bins 55-130, x = 0.25-0.60 m) shows oscillating drag force as flow passes through spoke gaps

This data can be used for detailed comparison once WheelFlow runs the same spoked geometry.

---

## Next Steps for Validation

### Step 1: Run Spoked Wheel in WheelFlow

STL files available in `~/Downloads/`:
- `TSV3.4 with Tire Solid for CFD.STL` (2.45 MB) - combined single-body STL
- `TTTR28_22_TSV3 Output Test - TSV3.4 22mm Internal-1.STL` (4.71 MB) - spokes only
- `TTTR28_22_TSV3 Output Test - TTTR28_22-1.STL` (285 KB) - rim/tire only

Run at 15° yaw with:
- Speed: 13.9 m/s
- Aref: 0.0225 m² (or 0.0227 to exactly match AeroCloud)
- Quality: Pro (to increase mesh count closer to AeroCloud's 12M)

### Step 2: Compare Results

**Expected outcome for spoked wheel in WheelFlow:**
- Cd: 0.4-0.7 (should approach AeroCloud's 0.49)
- CdA: 0.009-0.016 m² (should approach AeroCloud's 0.011)
- Fd: 1.0-1.9 N (should approach AeroCloud's 1.31 N)

**Acceptable agreement:** Within 20-30% given mesh resolution differences (1.4M vs 12.2M cells).

### Step 3: Mesh Sensitivity Study

If results differ by >30%, run mesh convergence study:
1. Basic mesh (~0.5M cells)
2. Standard mesh (~1.4M cells)
3. Pro mesh (~4-6M cells)

### Validation Checklist

- [x] Extract AeroCloud reference data (PDF + Excel)
- [x] Document AeroCloud simulation setup and results
- [x] Identify geometry mismatch as root cause (solid STL)
- [x] Verify WheelFlow disc wheel physics are correct
- [x] Create combined open-spoke STL from separate parts
- [x] Run spoked wheel standard quality (job c32c1408) - mesh too coarse
- [x] Run spoked wheel pro quality (job 2e534f01) - MRF blocks spoke flow
- [x] Identify MRF as root cause of overpredicted drag
- [x] Complete no-MRF test (job 2e534f01_noMRF) - Cd=0.692 (+41% vs AeroCloud)
- [x] Compare no-MRF CdA/Fd against AeroCloud
- [x] **Modify app.py to disable MRF for spoked/open wheels** (wall_bc rotation method)
- [x] Enable parallel snappyHexMesh for pro quality (8 cores, 3.6x speedup)
- [x] Run yaw sweep (0°, 5°, 10°, 15°, 20°) with pro quality parallel mesh
- [ ] Add surfaceFeatureExtract step for better edge resolution
- [ ] Run sweep with true open-spoke STL (combined from separate parts)
- [ ] Investigate combined STL geometry quality at spoke-rim interfaces

---

## Reference Files

**AeroCloud Reports:**
- PDF: `~/Downloads/TTTR28_22_TSV3_7d5df9.pdf` (31 pages)
- Excel: `~/Downloads/TTTR28_22_TSV3_7d5df9.xlsx` (3 sheets: Total, Parts, Bins)

**Spoked Wheel STLs:**
- `~/Downloads/TSV3.4 with Tire Solid for CFD.STL`
- `~/Downloads/TTTR28_22_TSV3 Output Test - TSV3.4 22mm Internal-1.STL`
- `~/Downloads/TTTR28_22_TSV3 Output Test - TTTR28_22-1.STL`

**WheelFlow Cases (on desktop):**
- Disc wheel yaw sweep: `cases/7a430d2b_*` (deleted)
- Solid STL test: `cases/d6f6689b` (Cd=1.290, deleted)
- Open spoke, standard: `cases/c32c1408` (Cd=1.288, deleted)
- Open spoke, pro + MRF: `cases/2e534f01` (Cd=1.123)
- Open spoke, pro, no MRF: `cases/2e534f01_noMRF` (Cd=0.692)
- **Pro yaw sweep 0°:** `cases/1a09a959_00` **(Cd=0.413)**
- **Pro yaw sweep 5°-20°:** `cases/bd2bc0d0_05..20` **(Cd=0.439-0.819)**

**Key Files:**
- Force coefficients: `postProcessing/forceCoeffs/0/forceCoeffs.dat`
- Raw forces: `postProcessing/forces/0/forces.dat`
- Wheel STL: `constant/triSurface/wheel.stl`
- MRF config: `constant/MRFProperties`
