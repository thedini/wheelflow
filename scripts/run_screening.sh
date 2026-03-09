#!/bin/bash
# Screening battery for CFD accuracy improvement study
# Submits 6 runs sequentially at 15° yaw, 200 iterations each
# Each run changes one variable from baseline

SERVER="http://localhost:8000"
FILE_ID="e8ece8bf"

submit_and_wait() {
    local name="$1"
    shift
    echo "=== Submitting: $name ==="

    # Submit job
    response=$(curl -s -X POST "$SERVER/api/simulate" \
        -F "file_id=$FILE_ID" \
        -F "name=$name" \
        -F "speed=13.9" \
        -F "yaw_angles=15" \
        -F "quality=pro" \
        -F "rotation_method=wall_bc" \
        -F "num_iterations=200" \
        "$@")

    job_id=$(echo "$response" | python3 -c "import json,sys; print(json.load(sys.stdin)['job_id'])")
    echo "Job ID: $job_id"

    # Wait for completion
    while true; do
        status=$(curl -s "$SERVER/api/jobs/$job_id" | python3 -c "import json,sys; print(json.load(sys.stdin).get('status','unknown'))")
        if [ "$status" = "complete" ]; then
            echo "$name: COMPLETE"
            # Print results
            curl -s "$SERVER/api/jobs/$job_id" | python3 -c "
import json, sys
j = json.load(sys.stdin)
r = j.get('results', {})
print(f'  Cd={r.get(\"Cd\",\"?\")}, Cs={r.get(\"Cs\",\"?\")}, Fd={r.get(\"Fd\",\"?\")}N, Fs={r.get(\"Fs\",\"?\")}N')
print(f'  Cells: {r.get(\"cell_count\",\"?\")}')
"
            break
        elif [ "$status" = "failed" ]; then
            echo "$name: FAILED"
            curl -s "$SERVER/api/jobs/$job_id" | python3 -c "import json,sys; print('  Error:', json.load(sys.stdin).get('error','unknown')[:200])"
            break
        fi
        sleep 30
    done
    echo ""
}

echo "========================================"
echo "CFD Accuracy Screening Battery"
echo "15° yaw, 200 iterations, pro quality"
echo "========================================"
echo ""

# Run A: Baseline (ALL old settings)
submit_and_wait "screen_A_baseline" \
    -F "k_inlet_override=0.1" \
    -F "omega_inlet_override=1.0" \
    -F "domain_mode=fixed" \
    -F "n_layers_override=3" \
    -F "included_angle=150"

# Run B: Only turbulence fix (k/omega computed, rest old)
submit_and_wait "screen_B_turb_fix" \
    -F "domain_mode=fixed" \
    -F "n_layers_override=3" \
    -F "included_angle=150"

# Run C: Only domain fix (scaled domain, rest old)
submit_and_wait "screen_C_domain_fix" \
    -F "k_inlet_override=0.1" \
    -F "omega_inlet_override=1.0" \
    -F "n_layers_override=3" \
    -F "included_angle=150"

# Run D: Only BL fix (10 layers, rest old)
submit_and_wait "screen_D_bl_fix" \
    -F "k_inlet_override=0.1" \
    -F "omega_inlet_override=1.0" \
    -F "domain_mode=fixed" \
    -F "included_angle=150"

# Run E: Only feature angle fix (120°, rest old)
submit_and_wait "screen_E_feature_fix" \
    -F "k_inlet_override=0.1" \
    -F "omega_inlet_override=1.0" \
    -F "domain_mode=fixed" \
    -F "n_layers_override=3"

# Run F: All fixes combined (all new defaults)
submit_and_wait "screen_F_all_fixes"

echo "========================================"
echo "Screening battery complete!"
echo "========================================"
