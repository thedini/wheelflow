"""
Tests for OpenFOAM environment configuration.

These tests verify that the library paths are set correctly for:
- Serial execution (can use dummy libs)
- Parallel execution (MUST NOT use dummy libs - breaks MPI)
"""

import pytest
from pathlib import Path

# Add backend to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app import get_openfoam_env, OPENFOAM_DIR


class TestOpenFOAMEnvironment:
    """Tests for OpenFOAM environment variable setup."""

    def test_serial_env_includes_dummy_libs(self):
        """Serial execution environment can include dummy libraries."""
        env = get_openfoam_env(parallel=False)

        ld_path = env.get("LD_LIBRARY_PATH", "")
        # Dummy libs are OK for serial runs
        assert f"{OPENFOAM_DIR}/platforms/linux64GccDPInt32Opt/lib" in ld_path

    def test_parallel_env_openmpi_before_dummy(self):
        """
        Parallel execution: openmpi-system MUST come BEFORE dummy in path.

        The dummy Pstream library breaks MPI, but other dummy libs (metis, etc.)
        are needed. By putting openmpi-system first, the linker finds the correct
        libPstream.so before reaching the dummy directory.
        """
        env = get_openfoam_env(parallel=True)

        ld_path = env.get("LD_LIBRARY_PATH", "")
        paths = ld_path.split(":")

        # Find positions of openmpi-system and dummy
        openmpi_idx = next((i for i, p in enumerate(paths) if 'openmpi-system' in p), -1)
        dummy_idx = next((i for i, p in enumerate(paths) if 'lib/dummy' in p), len(paths))

        # CRITICAL: openmpi-system must come BEFORE dummy
        assert openmpi_idx != -1, "openmpi-system not found in parallel LD_LIBRARY_PATH"
        assert openmpi_idx < dummy_idx, \
            f"openmpi-system (idx={openmpi_idx}) must come before dummy (idx={dummy_idx})"

    def test_parallel_env_includes_openmpi_libs(self):
        """Parallel execution should include OpenMPI libraries."""
        env = get_openfoam_env(parallel=True)

        ld_path = env.get("LD_LIBRARY_PATH", "")

        # OpenMPI libraries should be available
        assert "openmpi" in ld_path.lower() or \
               f"{OPENFOAM_DIR}/platforms/linux64GccDPInt32Opt/lib" in ld_path

    def test_openfoam_bin_in_path(self):
        """OpenFOAM binaries should be in PATH."""
        env = get_openfoam_env()

        path = env.get("PATH", "")
        assert "openfoam" in path.lower()

    def test_wm_project_dir_set(self):
        """WM_PROJECT_DIR should be set."""
        env = get_openfoam_env()

        assert "WM_PROJECT_DIR" in env
        assert Path(env["WM_PROJECT_DIR"]).exists()

    def test_gpu_env_includes_cuda_libs(self):
        """GPU-enabled environment should include CUDA libraries."""
        env = get_openfoam_env(gpu_enabled=True)

        ld_path = env.get("LD_LIBRARY_PATH", "")

        # CUDA libraries should be included
        assert "cuda" in ld_path.lower() or "amgx" in ld_path.lower()

    def test_parallel_gpu_env_openmpi_before_dummy(self):
        """Parallel + GPU: openmpi-system must still come before dummy."""
        env = get_openfoam_env(parallel=True, gpu_enabled=True)

        ld_path = env.get("LD_LIBRARY_PATH", "")
        paths = ld_path.split(":")

        openmpi_idx = next((i for i, p in enumerate(paths) if 'openmpi-system' in p), -1)
        dummy_idx = next((i for i, p in enumerate(paths) if 'lib/dummy' in p), len(paths))

        # CRITICAL: Even with GPU, openmpi-system must be before dummy
        assert openmpi_idx != -1, "openmpi-system not found in parallel+GPU LD_LIBRARY_PATH"
        assert openmpi_idx < dummy_idx, \
            f"openmpi-system (idx={openmpi_idx}) must come before dummy (idx={dummy_idx})"


class TestLibraryPathOrder:
    """Tests for library path ordering (important for dynamic linking)."""

    def test_openfoam_libs_before_system_libs(self):
        """OpenFOAM libraries should come before system libraries."""
        env = get_openfoam_env()

        ld_path = env.get("LD_LIBRARY_PATH", "")
        paths = ld_path.split(":")

        # Find indices of OpenFOAM and system lib paths
        of_idx = next((i for i, p in enumerate(paths) if "openfoam" in p.lower()), -1)
        sys_idx = next((i for i, p in enumerate(paths) if "/usr/lib" in p), len(paths))

        assert of_idx < sys_idx, \
            "OpenFOAM libs should come before system libs in LD_LIBRARY_PATH"


class TestParallelDecomposition:
    """Tests for parallel decomposition configuration."""

    def test_decompose_dict_generation(self, tmp_path):
        """Verify decomposeParDict is generated correctly."""
        from app import generate_decompose_dict

        case_dir = tmp_path / "test_case"
        system_dir = case_dir / "system"
        system_dir.mkdir(parents=True)

        generate_decompose_dict(case_dir, num_procs=8)

        decompose_dict = system_dir / "decomposeParDict"
        assert decompose_dict.exists()

        content = decompose_dict.read_text()
        assert "numberOfSubdomains 8" in content
        assert "scotch" in content.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
