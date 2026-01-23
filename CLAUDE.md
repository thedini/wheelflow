# WheelFlow - Bicycle Wheel CFD Analysis

## Project Overview
WheelFlow is a web application for computational fluid dynamics (CFD) analysis of bicycle wheels using OpenFOAM. It provides a user-friendly interface for uploading wheel geometries, configuring simulations, and visualizing aerodynamic results.

## Project Structure
```
wheelflow/
├── backend/
│   ├── app.py              # FastAPI application entry point
│   └── stl_validator.py    # STL file validation utilities
├── static/
│   ├── css/
│   │   ├── style.css       # Main UI styles
│   │   └── dashboard.css   # Results dashboard styles
│   └── js/
│       ├── app.js          # Main application logic
│       └── dashboard.js    # Dashboard visualization
├── templates/
│   ├── index.html          # Main upload/config page
│   └── results.html        # Results dashboard
├── tests/
│   ├── conftest.py         # Pytest fixtures
│   ├── test_stl_validator.py
│   ├── test_e2e_simulation.py
│   └── test_ui_playwright.py  # Browser E2E tests
├── docs/
│   ├── Bicycle_Wheel_CFD_Workflow.md
│   └── SESSION_CONTEXT.md
└── venv/                   # Python virtual environment (not in git)
```

## Running the Application

### Development Server
```bash
cd /home/constantine/repo/openFOAM/wheelflow
source venv/bin/activate
uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

### Running Tests
```bash
# All tests
pytest tests/ -v

# Playwright UI tests only
pytest tests/test_ui_playwright.py -v

# STL validation tests
pytest tests/test_stl_validator.py -v
```

## Key Features
- **STL Upload**: Drag & drop STL/OBJ geometry files with validation
- **3D Preview**: Three.js-based geometry visualization
- **Simulation Config**: Speed, yaw angles, ground simulation, wheel rotation
- **GPU Acceleration**: Optional AmgX support for RTX GPUs
- **Mesh Quality**: Basic/Standard/Pro mesh resolution options

## Technology Stack
- **Backend**: FastAPI (Python 3.8+)
- **Frontend**: Vanilla JS, Three.js for 3D
- **CFD**: OpenFOAM 13
- **Testing**: Pytest, Playwright

## OpenFOAM Integration
The application generates OpenFOAM cases with:
- blockMeshDict for domain creation
- snappyHexMeshDict for wheel geometry meshing
- simpleFoam solver configuration
- k-omega SST turbulence model

## OpenFOAM MCP Server (Optional)
For Claude Code integration, an MCP server is available at:
- Binary: `/home/constantine/repo/openfoam-mcp-server/build/openfoam-mcp-server-test`
- Provides CFD analysis tools accessible via Claude

## Development Notes
- Static files are served directly by FastAPI
- Browser cache may need clearing after CSS/JS changes (Ctrl+Shift+R)
- The server auto-reloads in development mode
