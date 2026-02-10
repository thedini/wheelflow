#!/bin/bash
# Test parallel snappyHexMesh configurations
# Run on desktop: bash tests/test_parallel_meshing.sh
#
# Tests serial vs parallel snappyHexMesh with different core counts
# and reconstruction strategies. Uses standard quality for fast iteration.

set -e

source /opt/openfoam13/etc/bashrc

BASE_DIR="/home/constantine/repo/openFOAM/wheelflow"
TEST_DIR="$BASE_DIR/cases/parallel_mesh_test"
TEMPLATE_CASE="$BASE_DIR/cases/f95b0a5c"
RESULTS_FILE="$TEST_DIR/results.csv"

# Use the same STL
STL_FILE="$BASE_DIR/uploads/de9928dc.stl"

echo "============================================"
echo "Parallel snappyHexMesh Test Suite"
echo "============================================"
echo "Template case: $TEMPLATE_CASE"
echo "Cores available: $(nproc)"
echo ""

mkdir -p "$TEST_DIR"
echo "mode,cores,mesh_time_sec,cell_count,max_non_ortho,snappy_exit_code,reconstruct_exit_code" > "$RESULTS_FILE"

# Create a fresh base case with blockMesh + surfaceFeatures already done
setup_base_case() {
    local case_dir="$1"
    local quality="$2"  # standard or pro

    rm -rf "$case_dir"
    mkdir -p "$case_dir"/{0,constant/triSurface,system}

    # Copy STL
    cp "$STL_FILE" "$case_dir/constant/triSurface/wheel.stl"

    # Copy field files and transport from template
    cp "$TEMPLATE_CASE/0/"* "$case_dir/0/" 2>/dev/null || true
    cp "$TEMPLATE_CASE/constant/transportProperties" "$case_dir/constant/" 2>/dev/null || true
    cp "$TEMPLATE_CASE/constant/turbulenceProperties" "$case_dir/constant/" 2>/dev/null || true
    cp "$TEMPLATE_CASE/constant/MRFProperties" "$case_dir/constant/" 2>/dev/null || true

    # controlDict
    cp "$TEMPLATE_CASE/system/controlDict" "$case_dir/system/"
    cp "$TEMPLATE_CASE/system/fvSchemes" "$case_dir/system/"
    cp "$TEMPLATE_CASE/system/fvSolution" "$case_dir/system/"

    # surfaceFeaturesDict
    cat > "$case_dir/system/surfaceFeaturesDict" << 'SFEEOF'
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      surfaceFeaturesDict;
}
surfaces ( "wheel.stl" );
includedAngle   150;
subsetFeatures { nonManifoldEdges yes; openEdges yes; }
trimFeatures { minElem 0; minLen 0; }
writeObj yes;
SFEEOF

    # blockMeshDict - use standard bg mesh for faster tests
    if [ "$quality" = "pro" ]; then
        local BG="(120 60 42)"
        local MAX_GLOBAL=15000000
        local SURF_MIN=4
        local SURF_MAX=6
        local NCELLS=3
    else
        local BG="(70 35 25)"
        local MAX_GLOBAL=2000000
        local SURF_MIN=3
        local SURF_MAX=4
        local NCELLS=3
    fi

    cat > "$case_dir/system/blockMeshDict" << BMEOF
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      blockMeshDict;
}
scale 1;
vertices
(
    (-2 -1.5 0)
    ( 5 -1.5 0)
    ( 5  1.5 0)
    (-2  1.5 0)
    (-2 -1.5 2)
    ( 5 -1.5 2)
    ( 5  1.5 2)
    (-2  1.5 2)
);
blocks
(
    hex (0 1 2 3 4 5 6 7) $BG simpleGrading (1 1 1)
);
edges ();
boundary
(
    inlet  { type patch; faces ((0 4 7 3)); }
    outlet { type patch; faces ((1 2 6 5)); }
    ground { type wall;  faces ((0 1 2 3)); }
    top    { type patch; faces ((4 5 6 7)); }
    sides  { type patch; faces ((0 1 5 4) (3 7 6 2)); }
);
BMEOF

    # snappyHexMeshDict
    cat > "$case_dir/system/snappyHexMeshDict" << SHEOF
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      snappyHexMeshDict;
}
castellatedMesh true;
snap            true;
addLayers       true;
geometry
{
    wheel
    {
        type triSurfaceMesh;
        file "wheel.stl";
    }
    refinementBox
    {
        type searchableBox;
        min (-0.5 -0.6 0);
        max (2.0 0.6 1.0);
    }
    wakeRegion
    {
        type searchableBox;
        min (0.3 -0.3 0);
        max (3.0 0.3 0.8);
    }
    rotatingZone
    {
        type searchableCylinder;
        point1 (0 -0.1 0.325);
        point2 (0 0.1 0.325);
        radius 0.341;
    }
}
castellatedMeshControls
{
    maxLocalCells 2000000;
    maxGlobalCells $MAX_GLOBAL;
    minRefinementCells 10;
    nCellsBetweenLevels $NCELLS;
    features
    (
        { file "wheel.eMesh"; level $SURF_MAX; }
    );
    refinementSurfaces
    {
        wheel
        {
            level ($SURF_MIN $SURF_MAX);
            patchInfo { type wall; }
        }
    }
    resolveFeatureAngle 30;
    refinementRegions
    {
        refinementBox
        {
            mode inside;
            levels ((1E15 $(($SURF_MIN - 1))));
        }
        wakeRegion
        {
            mode inside;
            levels ((1E15 $SURF_MIN));
        }
        rotatingZone
        {
            mode inside;
            levels ((1E15 $SURF_MIN));
        }
    }
    locationInMesh (0.5 0 0.5);
    allowFreeStandingZoneFaces true;
}
snapControls
{
    nSmoothPatch 3;
    tolerance 2.0;
    nSolveIter 50;
    nRelaxIter 5;
    nFeatureSnapIter 10;
    implicitFeatureSnap false;
    explicitFeatureSnap true;
    multiRegionFeatureSnap false;
}
addLayersControls
{
    relativeSizes true;
    layers
    {
        wheel { nSurfaceLayers 3; }
        ground { nSurfaceLayers 2; }
    }
    expansionRatio 1.2;
    finalLayerThickness 0.3;
    minThickness 0.1;
    nGrow 0;
    featureAngle 60;
    nRelaxIter 3;
    nSmoothSurfaceNormals 1;
    nSmoothNormals 3;
    nSmoothThickness 10;
    maxFaceThicknessRatio 0.5;
    maxThicknessToMedialRatio 0.3;
    minMedianAxisAngle 90;
    nBufferCellsNoExtrude 0;
    nLayerIter 50;
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
mergeTolerance 1e-6;
SHEOF

    # decomposeParDict
    cat > "$case_dir/system/decomposeParDict" << 'DPEOF'
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      decomposeParDict;
}
numberOfSubdomains  NPROCS_PLACEHOLDER;
method          scotch;
DPEOF

    # Run blockMesh
    echo "  Running blockMesh..."
    blockMesh -case "$case_dir" > "$case_dir/log.blockMesh" 2>&1

    # Run surfaceFeatures
    echo "  Running surfaceFeatures..."
    surfaceFeatures -case "$case_dir" > "$case_dir/log.surfaceFeatures" 2>&1

    echo "  Base case ready."
}

# Run a single test
run_test() {
    local mode="$1"    # serial, parallel, parallel_redistribute
    local nprocs="$2"
    local quality="$3"
    local case_name="${mode}_${nprocs}cores_${quality}"
    local case_dir="$TEST_DIR/$case_name"

    echo ""
    echo "--------------------------------------------"
    echo "Test: $case_name"
    echo "--------------------------------------------"

    # Set up fresh case
    setup_base_case "$case_dir" "$quality"

    local snappy_exit=0
    local reconstruct_exit=0
    local start_time=$(date +%s)

    if [ "$mode" = "serial" ]; then
        echo "  Running snappyHexMesh (serial)..."
        snappyHexMesh -overwrite -case "$case_dir" > "$case_dir/log.snappyHexMesh" 2>&1 || snappy_exit=$?

    elif [ "$mode" = "parallel" ]; then
        # Standard parallel: decompose -> snappy -> reconstruct
        sed -i "s/NPROCS_PLACEHOLDER/$nprocs/" "$case_dir/system/decomposeParDict"

        echo "  Decomposing ($nprocs cores)..."
        decomposePar -case "$case_dir" > "$case_dir/log.decomposePar" 2>&1

        echo "  Running snappyHexMesh (parallel, $nprocs cores)..."
        mpirun -np "$nprocs" snappyHexMesh -parallel -overwrite -case "$case_dir" > "$case_dir/log.snappyHexMesh" 2>&1 || snappy_exit=$?

        if [ $snappy_exit -eq 0 ]; then
            echo "  Reconstructing mesh..."
            reconstructParMesh -constant -case "$case_dir" > "$case_dir/log.reconstructParMesh" 2>&1 || reconstruct_exit=$?
            # Clean up processor dirs
            rm -rf "$case_dir"/processor*
        fi

    elif [ "$mode" = "parallel_noreconstruct" ]; then
        # Parallel without reconstruct - check if -overwrite works in parallel
        sed -i "s/NPROCS_PLACEHOLDER/$nprocs/" "$case_dir/system/decomposeParDict"

        echo "  Decomposing ($nprocs cores)..."
        decomposePar -case "$case_dir" > "$case_dir/log.decomposePar" 2>&1

        echo "  Running snappyHexMesh (parallel, $nprocs cores, no reconstruct)..."
        mpirun -np "$nprocs" snappyHexMesh -parallel -overwrite -case "$case_dir" > "$case_dir/log.snappyHexMesh" 2>&1 || snappy_exit=$?

        if [ $snappy_exit -eq 0 ]; then
            echo "  Reconstructing mesh (mergeTol)..."
            reconstructParMesh -constant -mergeTol 1e-6 -case "$case_dir" > "$case_dir/log.reconstructParMesh" 2>&1 || reconstruct_exit=$?
            rm -rf "$case_dir"/processor*
        fi
    fi

    local end_time=$(date +%s)
    local elapsed=$(( end_time - start_time ))

    # Get cell count and mesh quality
    local cell_count=0
    local max_nonortho="N/A"
    if [ $snappy_exit -eq 0 ] && [ $reconstruct_exit -eq 0 ]; then
        echo "  Running checkMesh..."
        checkMesh -case "$case_dir" > "$case_dir/log.checkMesh" 2>&1 || true
        cell_count=$(grep "cells:" "$case_dir/log.checkMesh" 2>/dev/null | head -1 | awk '{print $NF}')
        max_nonortho=$(grep "Max non-orthogonality" "$case_dir/log.checkMesh" 2>/dev/null | awk '{print $NF}')
    fi

    echo ""
    echo "  RESULTS:"
    echo "  Mode:           $mode"
    echo "  Cores:          $nprocs"
    echo "  Quality:        $quality"
    echo "  Time:           ${elapsed}s"
    echo "  Cells:          $cell_count"
    echo "  Max non-ortho:  $max_nonortho"
    echo "  Snappy exit:    $snappy_exit"
    echo "  Reconstruct:    $reconstruct_exit"

    echo "$mode,$nprocs,$elapsed,$cell_count,$max_nonortho,$snappy_exit,$reconstruct_exit" >> "$RESULTS_FILE"
}

# ============================================
# Test matrix
# ============================================

echo ""
echo "Phase 1: Standard quality (~2M cells) - fast iteration"
echo "======================================================="

# Baseline: serial
run_test "serial" 1 "standard"

# Parallel with different core counts
run_test "parallel" 4 "standard"
run_test "parallel" 8 "standard"
run_test "parallel" 16 "standard"

# Parallel with mergeTol reconstruction
run_test "parallel_noreconstruct" 8 "standard"

echo ""
echo "Phase 2: Pro quality (~12M cells) - production test"
echo "===================================================="

# Serial pro (will be slow - skip if standard tests show parallel works)
# run_test "serial" 1 "pro"

# Parallel pro with best core count from phase 1
run_test "parallel" 8 "pro"
run_test "parallel" 16 "pro"

echo ""
echo "============================================"
echo "ALL TESTS COMPLETE"
echo "============================================"
echo ""
echo "Results saved to: $RESULTS_FILE"
cat "$RESULTS_FILE" | column -t -s,
