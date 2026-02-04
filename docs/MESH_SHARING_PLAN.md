# Mesh Sharing for Batch Yaw Simulations

## Current Problem

Each yaw angle simulation in a batch currently runs the **full pipeline**:
1. blockMesh (~10 sec)
2. snappyHexMesh (~7 min)
3. topoSet (~5 sec)
4. decomposePar (~30 sec)
5. foamRun (~18 min)

**Total per yaw angle: ~26 minutes**
**Batch of 5 yaw angles: ~130 minutes**

## Optimization Opportunity

For different yaw angles, only **boundary conditions change** - the mesh is identical:
- Same wheel geometry (STL)
- Same domain size
- Same refinement regions
- Same MRF cellZone

Only these files change between yaw angles:
- `0/U` - inlet velocity direction
- `system/controlDict` - dragDir for force calculation
- `constant/MRFProperties` - (same omega, different reference frame orientation)

## Proposed Solution

### Phase 1: Mesh Reuse via Copy

```
Batch Simulation Flow (Optimized):

Job 1 (0° yaw):
  ├── blockMesh ────────┐
  ├── snappyHexMesh ────┼── Mesh created once
  ├── topoSet ──────────┘
  ├── Update BCs for 0°
  ├── decomposePar
  └── foamRun

Job 2 (5° yaw):
  ├── Copy mesh from Job 1  ← Skip meshing!
  ├── Update BCs for 5°
  ├── decomposePar
  └── foamRun

Job 3-N: Same as Job 2
```

### Implementation Details

#### 1. Modify `run_batch_simulation()` in `app.py`

```python
async def run_batch_simulation(batch_id: str, job_ids: list):
    """Run batch simulation with mesh sharing."""
    batch = batch_jobs[batch_id]
    base_mesh_dir = None

    try:
        for i, job_id in enumerate(job_ids):
            batch["status"] = f"running_{i+1}_of_{len(job_ids)}"
            job = jobs[job_id]
            config = job["config"]
            case_dir = CASES_DIR / job_id

            if i == 0:
                # First job: Full simulation including mesh
                await run_simulation(job_id)
                base_mesh_dir = case_dir
            else:
                # Subsequent jobs: Copy mesh, update BCs only
                await run_simulation_with_shared_mesh(job_id, base_mesh_dir)

    except Exception as e:
        batch["status"] = "failed"
        batch["error"] = str(e)
```

#### 2. New Function: `run_simulation_with_shared_mesh()`

```python
async def run_simulation_with_shared_mesh(job_id: str, base_mesh_dir: Path):
    """Run simulation reusing mesh from base case."""
    job = jobs[job_id]
    config = job["config"]
    case_dir = CASES_DIR / job_id

    # Create case directory structure
    case_dir.mkdir(exist_ok=True)
    for subdir in ["0", "constant", "system"]:
        (case_dir / subdir).mkdir(exist_ok=True)

    # Copy mesh files from base case
    shutil.copytree(
        base_mesh_dir / "constant" / "polyMesh",
        case_dir / "constant" / "polyMesh"
    )

    # Copy cellZones (for MRF)
    # Already included in polyMesh

    # Generate case files with new yaw angle BCs
    await generate_case_files(case_dir, config)

    # Run solver only (skip meshing)
    job["status"] = "solving"
    await run_openfoam_command(
        case_dir, "foamRun",
        ["-solver", "incompressibleFluid"],
        parallel=True, num_procs=16
    )
```

#### 3. Files to Copy vs Generate

**Copy from base mesh:**
```
constant/polyMesh/
  ├── boundary
  ├── cellZones       # MRF zone
  ├── faces
  ├── faceZones
  ├── neighbour
  ├── owner
  ├── points
  └── pointZones
```

**Generate fresh for each yaw angle:**
```
0/
  ├── U              # Different inlet velocity direction
  ├── p
  ├── k
  ├── omega
  └── nut

system/
  ├── controlDict    # Different dragDir for forceCoeffs
  ├── fvSchemes
  ├── fvSolution
  └── decomposeParDict

constant/
  ├── momentumTransport
  ├── physicalProperties
  └── MRFProperties
```

### Expected Performance Improvement

| Stage | Current (per job) | Optimized (job 2+) |
|-------|-------------------|-------------------|
| blockMesh | 10 sec | 0 (skipped) |
| snappyHexMesh | 7 min | 0 (skipped) |
| topoSet | 5 sec | 0 (skipped) |
| Copy mesh | - | ~30 sec |
| decomposePar | 30 sec | 30 sec |
| foamRun | 18 min | 18 min |
| **Total** | **~26 min** | **~19 min** |

**Batch of 5 yaw angles:**
- Current: 5 × 26 = **130 minutes**
- Optimized: 26 + 4 × 19 = **102 minutes** (22% faster)

### Phase 2: Parallel Yaw Simulations (Future)

Once mesh sharing works, multiple yaw angles could run **in parallel** if resources allow:

```
Job 1 (0°):  [mesh]──[solve]
Job 2 (5°):  [wait]──[copy]──[solve]
Job 3 (10°): [wait]──[copy]──────────[solve]
Job 4 (15°): [wait]──[copy]────────────────[solve]
```

With 64 cores, could run 4 yaw angles simultaneously (16 cores each).

### Edge Cases to Handle

1. **First job fails during meshing**: Abort entire batch
2. **Mesh copy fails**: Fall back to full mesh generation
3. **Different wheel geometry between jobs**: Detect and regenerate mesh
4. **MRF cellZone missing**: Ensure topoSet output is included in copy

### Testing Plan

1. Unit test: Verify mesh files are identical after copy
2. Integration test: Run 2-angle batch, compare results with separate runs
3. Performance test: Measure actual time savings

## Implementation Priority

1. **MVP**: Copy entire `constant/polyMesh` directory
2. **Optimization**: Only copy necessary files
3. **Advanced**: Parallel yaw simulations
