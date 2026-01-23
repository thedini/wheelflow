"""
PIMPLE Solver Settings for Transient Wheel Simulation

When using AMI for wheel rotation, we need a transient solver (pimpleFoam)
instead of the steady-state simpleFoam.

PIMPLE = PISO + SIMPLE
- Uses SIMPLE-style relaxation within each time step
- Uses PISO-style pressure correction
- More stable than pure PISO for larger time steps
"""

from typing import Tuple


def generate_pimple_fv_solution(quality: str = "standard",
                                  gpu_enabled: bool = False,
                                  base_dir: str = "") -> str:
    """
    Generate fvSolution for pimpleFoam solver.

    Args:
        quality: Mesh quality preset (basic, standard, pro)
        gpu_enabled: Whether to use GPU acceleration for pressure
        base_dir: Base directory for GPU config file

    Returns:
        fvSolution dictionary content
    """
    # Quality-dependent settings
    if quality == "pro":
        relax_U, relax_p, relax_k = 0.7, 0.3, 0.7
        n_correctors = 3
        n_outer = 2
        solver_tol = "1e-07"
    elif quality == "standard":
        relax_U, relax_p, relax_k = 0.8, 0.4, 0.8
        n_correctors = 2
        n_outer = 1
        solver_tol = "1e-06"
    else:  # basic
        relax_U, relax_p, relax_k = 0.9, 0.5, 0.9
        n_correctors = 2
        n_outer = 1
        solver_tol = "1e-06"

    # Pressure solver
    if gpu_enabled:
        pressure_solver = f'''    p
    {{
        solver          AmgX;
        configFile      "{base_dir}/backend/gpu/amgx_pressure.json";
        tolerance       {solver_tol};
        relTol          0.01;
    }}

    pFinal
    {{
        $p;
        relTol          0;
    }}'''
    else:
        pressure_solver = f'''    p
    {{
        solver          GAMG;
        smoother        GaussSeidel;
        tolerance       {solver_tol};
        relTol          0.01;
        nPreSweeps      0;
        nPostSweeps     2;
        cacheAgglomeration true;
        agglomerator    faceAreaPair;
        nCellsInCoarsestLevel 100;
        mergeLevels     1;
    }}

    pFinal
    {{
        $p;
        relTol          0;
    }}'''

    fv_solution = f'''FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      fvSolution;
}}

solvers
{{
{pressure_solver}

    "(U|k|omega)"
    {{
        solver          PBiCGStab;
        preconditioner  DILU;
        tolerance       {solver_tol};
        relTol          0.1;
    }}

    "(U|k|omega)Final"
    {{
        $U;
        relTol          0;
    }}

    Phi
    {{
        solver          GAMG;
        smoother        GaussSeidel;
        tolerance       1e-06;
        relTol          0.01;
    }}
}}

PIMPLE
{{
    nOuterCorrectors    {n_outer};
    nCorrectors         {n_correctors};
    nNonOrthogonalCorrectors 1;

    // Relaxation within PIMPLE loop
    relaxationFactors
    {{
        fields
        {{
            p               {relax_p};
        }}
        equations
        {{
            U               {relax_U};
            k               {relax_k};
            omega           {relax_k};
        }}
    }}

    // Convergence control (exit outer loop early if converged)
    residualControl
    {{
        p
        {{
            tolerance   1e-4;
            relTol      0;
        }}
        U
        {{
            tolerance   1e-4;
            relTol      0;
        }}
        "(k|omega)"
        {{
            tolerance   1e-4;
            relTol      0;
        }}
    }}
}}

relaxationFactors
{{
    // Final iteration uses no relaxation
    fields
    {{
        p               1;
    }}
    equations
    {{
        U               1;
        k               1;
        omega           1;
    }}
}}
'''
    return fv_solution


def generate_transient_control_dict(speed: float,
                                     yaw: float,
                                     wheel_radius: float,
                                     air_rho: float,
                                     aref: float,
                                     end_time: float = 2.0,
                                     delta_t: float = 0.001,
                                     write_interval: float = 0.1) -> str:
    """
    Generate controlDict for transient simulation.

    For rotating wheel simulation, we want to simulate at least 1-2 full rotations
    to reach periodic steady state.

    Args:
        speed: Flow speed (m/s)
        yaw: Yaw angle (degrees)
        wheel_radius: Wheel radius (m)
        air_rho: Air density (kg/m³)
        aref: Reference area (m²)
        end_time: Simulation end time (s)
        delta_t: Time step (s)
        write_interval: Output write interval (s)

    Returns:
        controlDict content
    """
    import math

    yaw_rad = math.radians(yaw)
    vx = speed * math.cos(yaw_rad)
    vy = speed * math.sin(yaw_rad)

    # Calculate rotation period
    omega = speed / wheel_radius
    rotation_period = 2 * math.pi / omega

    control_dict = f'''FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      controlDict;
}}

application     pimpleFoam;

startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         {end_time};  // ~{end_time / rotation_period:.1f} wheel rotations

deltaT          {delta_t};

writeControl    adjustableRunTime;
writeInterval   {write_interval};

purgeWrite      5;
writeFormat     ascii;
writePrecision  8;
writeCompression off;
timeFormat      general;
timePrecision   6;

runTimeModifiable true;

// Adaptive time stepping (useful for AMI)
adjustTimeStep  yes;
maxCo           0.9;
maxDeltaT       {delta_t * 10};

functions
{{
    forceCoeffs
    {{
        type            forceCoeffs;
        libs            ("libforces.so");
        writeControl    timeStep;
        writeInterval   10;

        patches         (wheel);
        rho             rhoInf;
        rhoInf          {air_rho};

        CofR            (0 0 {wheel_radius});
        liftDir         (0 0 1);
        dragDir         ({vx/speed:.6f} {vy/speed:.6f} 0);
        pitchAxis       (0 1 0);

        magUInf         {speed};
        lRef            {wheel_radius * 2};
        Aref            {aref};
    }}

    // Field averaging for time-averaged results
    fieldAverage1
    {{
        type            fieldAverage;
        libs            ("libfieldFunctionObjects.so");
        writeControl    writeTime;
        timeStart       {end_time * 0.5};  // Start averaging after 50% of simulation

        fields
        (
            U
            {{
                mean        on;
                prime2Mean  on;
                base        time;
            }}
            p
            {{
                mean        on;
                prime2Mean  on;
                base        time;
            }}
        );
    }}
}}

// Wheel rotation info
// Angular velocity: {omega:.2f} rad/s
// Rotation period: {rotation_period:.3f} s
// Simulating {end_time / rotation_period:.1f} rotations
'''
    return control_dict


def generate_transient_fv_schemes(quality: str = "standard") -> str:
    """
    Generate fvSchemes for transient simulation.

    Uses second-order time discretization for accuracy.
    """
    # Quality-dependent spatial schemes
    if quality == "pro":
        sn_grad = "limited corrected 0.5"
        laplacian = "Gauss linear limited corrected 0.5"
        grad_scheme = "cellLimited Gauss linear 1"
    elif quality == "standard":
        sn_grad = "limited corrected 0.33"
        laplacian = "Gauss linear limited corrected 0.33"
        grad_scheme = "cellLimited Gauss linear 1"
    else:
        sn_grad = "corrected"
        laplacian = "Gauss linear corrected"
        grad_scheme = "Gauss linear"

    fv_schemes = f'''FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      fvSchemes;
}}

ddtSchemes
{{
    default         backward;  // Second-order implicit for transient
}}

gradSchemes
{{
    default         {grad_scheme};
    grad(U)         {grad_scheme};
    grad(k)         {grad_scheme};
    grad(omega)     {grad_scheme};
}}

divSchemes
{{
    default         none;
    div(phi,U)      Gauss linearUpwindV grad(U);
    div(phi,k)      Gauss upwind;
    div(phi,omega)  Gauss upwind;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}}

laplacianSchemes
{{
    default         {laplacian};
}}

interpolationSchemes
{{
    default         linear;
}}

snGradSchemes
{{
    default         {sn_grad};
}}

wallDist
{{
    method          meshWave;
}}
'''
    return fv_schemes
