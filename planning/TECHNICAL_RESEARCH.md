# Technical Research: Bicycle Wheel CFD Simulation

## Executive Summary

This document compiles research from academic papers, industry documentation, and community discussions to inform the development of WheelFlow, a bicycle wheel CFD analysis platform.

---

## Industry Landscape

### Existing CFD Platforms for Cycling

| Platform | Type | Key Features |
|----------|------|--------------|
| **AeroCloud (NablaFlow)** | Cloud SaaS | Sports-focused, wheel rotation, yaw sweeps, automated reporting |
| **Bramble CFD** | Cloud SaaS | TotalSim heritage, cycling-specific, comparison tools, OpenFOAM-based |
| **SimScale** | Cloud SaaS | General CFD, public projects, community |
| **OpenFOAM** | Open Source | Full control, steep learning curve, basis for many platforms |

Sources: [NablaFlow](https://nablaflow.io/aerocloud/), [Bramble CFD](https://bramblecfd.com/cycling-aerodynamics/), [SimScale](https://www.simscale.com/projects/Akrem/bike_aerodynamics_1/)

---

## Mesh Best Practices for Wheel CFD

### Surface Grid Requirements
Based on research from [CFD simulations of spoked wheel aerodynamics (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S0167610519305884):

| Parameter | Recommended Value | Notes |
|-----------|------------------|-------|
| **y+ value** | < 4 | Critical for accurate results |
| **Far-field growth rate** | ≤ 1.15 | High sensitivity observed |
| **Total cell count** | ~8 million | Optimal for wheel analysis |
| **Prism layers** | 15 cells | 1.2 growth rate |

### Quality Levels (Mapped to WheelFlow)
| Level | Cell Count | Use Case |
|-------|-----------|----------|
| Basic | ~500k | Quick screening |
| Standard | ~2M | Design iteration |
| Pro | ~6M+ | Final validation |

---

## Turbulence Model Selection

### Recommended Models
Based on academic validation studies:

1. **k-ω SST** - Best overall accuracy for separated flows
2. **γ-SST (Transition SST)** - Good for transitional boundary layers
3. **Realizable k-ε** - Robust, good for complex geometries
4. **Spalart-Allmaras** - Low Reynolds number, resolves viscous sublayer

### Validation Results
- CFD vs wind tunnel agreement: ~5% margin on drag coefficient
- Scale-adaptive simulations (SAS) show satisfactory agreement
- Steady RANS with SST k-ω provides good accuracy

Source: [CFD simulations of cyclist aerodynamics (ScienceDirect 2024)](https://www.sciencedirect.com/science/article/pii/S0167610524000771)

---

## Wheel Rotation Modeling

### Methods Comparison

| Method | Pros | Cons | Accuracy |
|--------|------|------|----------|
| **MRF (Moving Reference Frame)** | Steady-state, fast | Position-dependent, pressure gradient issues | +9.7% deviation |
| **Hybrid MRF-RW** | Better accuracy | More complex setup | -2.1% deviation |
| **rotatingWallVelocity** | Simple BC | Only tangential velocity | Limited on normal surfaces |
| **Sliding Mesh (AMI)** | Most accurate | Computationally expensive, transient | Best |

### OpenFOAM Implementation
From [OpenFOAM Rotating Machinery Guide](https://www.tfd.chalmers.se/~hani/kurser/OS_CFD_2015/HakanNilssonRotatingMachineryTrainingOFW10.pdf):

```
// MRFProperties example
MRF_wheel
{
    active    true;
    cellZone  wheelZone;
    origin    (0 0 0.325);  // Wheel center
    axis      (0 1 0);       // Rotation axis (lateral)
    omega     -43.0;         // rad/s for 50 km/h, r=0.325m
}
```

### Wheel Angular Velocity Calculation
```
ω = V / r

Where:
- V = forward velocity (m/s)
- r = wheel radius (m)
- ω = angular velocity (rad/s)

Example: V=13.9 m/s, r=0.325m → ω = 42.8 rad/s
```

---

## Boundary Conditions

### Standard Setup
From research and industry practice:

| Boundary | Type | Value |
|----------|------|-------|
| **Inlet** | Velocity inlet | V_freestream at yaw angle |
| **Outlet** | Pressure outlet | p = 0 (gauge) |
| **Ground** | Moving wall / Slip | V_ground = V_freestream × cos(yaw) |
| **Top/Sides** | Symmetry / Slip | Zero normal gradient |
| **Wheel surfaces** | No-slip wall | With rotation BC |

### Yaw Angle Implementation
```
// Velocity components for yaw angle θ
U_x = V × cos(θ)
U_y = V × sin(θ)
U_z = 0
```

### Domain Size Recommendations
From Bramble CFD: 100m long × 50m wide × 25m tall (adjustable)

---

## Key Aerodynamic Parameters

### Force Components
| Symbol | Name | Description |
|--------|------|-------------|
| **Fd** | Drag Force | Force opposing motion (N) |
| **Fl** | Lift Force | Vertical force (N) |
| **Fs** | Side Force | Lateral force (N) |

### Coefficients
```
Cd = Fd / (0.5 × ρ × V² × A)
Cl = Fl / (0.5 × ρ × A)
Cs = Fs / (0.5 × ρ × V² × A)

Where:
- ρ = 1.225 kg/m³ (ISO standard atmosphere)
- V = freestream velocity (m/s)
- A = reference area (m²)
```

### Drag Area (CdA)
The most commonly used metric in cycling aerodynamics:
```
CdA = Cd × A = Fd / (0.5 × ρ × V²)
```

### Key Finding
Wheels contribute approximately **10-15% of total cyclist-bicycle drag**. Optimizing wheel design can achieve **>3% overall drag reduction**.

Source: [Greenwell et al., cited in ScienceDirect research](https://www.sciencedirect.com/science/article/pii/S0167610519305884)

---

## Ground Effect Modeling

### Wheel/Ground Contact Options
From [CFD simulations of cycling wheel ground contact (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S0997754619306144):

1. **Small clearance** - Gap between tire and ground
2. **Contact patch** - Solid contact region
3. **Moving ground** - Belt matching wheel rotation speed
4. **Slip ground** - Simplified, no boundary layer

### AeroCloud Ground Settings
- Ground toggle: On/Off
- Ground type: Slip / Moving belt
- Ground offset: Distance from wheel bottom

---

## Results Visualization Best Practices

### Pressure Coefficient (Cp)
```
Cp = (p - p_∞) / (0.5 × ρ × V²)

Color scale typically: -0.6 to 1.0
```

### Flow Visualization
1. **Pressure contours** - Surface pressure distribution
2. **Streamlines** - Flow path visualization
3. **Wake profiles** - Velocity deficit behind wheel
4. **Slices** - Cross-sectional views at various positions

### AeroCloud Slice Fields
- Total Pressure Coefficient
- Total Pressure Coefficient + LIC (Line Integral Convolution)
- Static Pressure Coefficient
- Acoustic Power (Beta)

---

## Comparison Tool Features (Bramble CFD Reference)

Key features from Bramble that could inform WheelFlow development:

1. **Switcher Tool** - Toggle between simulation runs to reveal subtle differences
2. **Delta Plots** - Generate difference plots between any two simulations
3. **Side-by-side Comparison** - Multiple simulations in parallel view
4. **Meancalc Integration** - Automatic convergence monitoring and stopping

---

## Data Export Formats

### Industry Standard Outputs
| Format | Use Case |
|--------|----------|
| **VTK** | ParaView visualization |
| **CSV/Excel** | Numerical data analysis |
| **PDF Report** | Client deliverables |
| **Images** | Documentation, presentations |

### AeroCloud Export Options
- PDF Report (automated)
- Excel Spreadsheet (all numerical data)
- Slice Images
- Raw VTK Data

---

## Community Resources

### Forums & Discussions
- [Slowtwitch Forum - Wheel CFD Discussion](https://forum.slowtwitch.com/t/an-aerodynamic-study-of-bicycle-wheel-performance-using-cfd/606029)
- [CFD Online - OpenFOAM Tutorials](https://www.cfd-online.com/Forums/openfoam-community-contributions/239897-openfoam-tutorial-mrf-approach-simulation-mixing-tank.html)

### Academic References
1. CFD simulations of spoked wheel aerodynamics - Sensitivity analysis framework
2. CFD simulations of cyclist aerodynamics - Best practice guidelines
3. Bicycle wheel aerodynamics predictions - Validation studies

### GitHub Resources
- [OpenFOAM Official](https://github.com/OpenFOAM) - Official repository
- [CfdOF](https://github.com/jaheyns/CfdOF) - FreeCAD integration
- [CFDTool](https://github.com/precise-simulation/cfdtool) - Easy-to-use GUI

---

## Recommendations for WheelFlow

### Short-term (MVP)
1. Implement k-ω SST turbulence model as default
2. Use MRF for wheel rotation (fastest, acceptable accuracy)
3. Support Basic/Standard/Pro mesh quality levels
4. Display Fd, Fl, Fs and calculated coefficients

### Medium-term
1. Add hybrid MRF-RW option for better accuracy
2. Implement pressure coefficient visualization
3. Add yaw sweep automation
4. Create PDF/Excel export

### Long-term
1. Sliding mesh (AMI) option for highest accuracy
2. Comparison tools (inspired by Bramble's switcher)
3. Convergence monitoring (Meancalc-style)
4. 3D interactive post-processing

