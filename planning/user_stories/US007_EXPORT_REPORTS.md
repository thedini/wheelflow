# User Story: US-007 - Export Reports and Data

## Title
Export Simulation Results as PDF Reports and Excel Data

## Priority
**HIGH** - Essential for professional use

## User Story
As a **wheel designer presenting results to stakeholders**, I want to **export my simulation results as professional PDF reports and data spreadsheets** so that I can **share findings with team members, clients, and for documentation**.

---

## Acceptance Criteria

### AC1: PDF Report Export
- [ ] Generate branded PDF report
- [ ] Include simulation metadata (name, date, parameters)
- [ ] Include key metrics table (forces, coefficients)
- [ ] Include input parameters summary
- [ ] Include visualizations (pressure plots, graphs)
- [ ] Add WheelFlow branding/header

### AC2: Excel/CSV Export
- [ ] Export all numerical data to Excel (.xlsx)
- [ ] Include summary sheet with key metrics
- [ ] Include raw force data
- [ ] Include per-yaw-angle breakdown
- [ ] Support CSV format option

### AC3: Image Export
- [ ] Export pressure slice images (PNG/JPG)
- [ ] Export force distribution graph
- [ ] Export 3D view screenshot
- [ ] Batch export all slices as ZIP

### AC4: Download UI
- [ ] Download dropdown menu with format options
- [ ] Progress indicator for large exports
- [ ] Automatic file naming (SimName_Date.pdf)

---

## Technical Notes

### PDF Report Structure
Based on AeroCloud report format:

```
Page 1: Cover
- Title: Simulation Report
- Simulation name
- Date
- WheelFlow branding

Page 2: Executive Summary
- Key metrics table
- Input parameters
- 3D model preview

Page 3: Force Results
- Force values table (all yaw angles)
- Coefficient values
- CdA comparison

Page 4-N: Visualizations
- Pressure contour plots
- Force distribution graph
- Slice views (selected)

Final Page: Methodology
- Mesh quality
- Turbulence model
- Boundary conditions
```

### Excel Structure
```
Sheet 1: Summary
- Simulation info
- Key metrics

Sheet 2: Forces
- Yaw | Fd | Fl | Fs | Md | Ml | Ms

Sheet 3: Coefficients
- Yaw | Cd | Cl | Cs | CdA | ClA | CsA

Sheet 4: Input Parameters
- All simulation settings
```

### Reference Implementation
AeroCloud export options:
- Download Report (PDF)
- Download Spreadsheet (Excel)
- Slice images (may expire)
- Raw data (VTK format, may expire)

---

## UI Mockup Specification

```
┌─────────────────────────────────────────────────────────────┐
│ TTTR28_22_TSV3                                              │
│ Completed - Jan 23, 2025                                    │
├─────────────────────────────────────────────────────────────┤
│                                        [Share]  [Download ▼]│
│                                                 ┌───────────┤
│                                                 │ 📄 Report │
│                                                 │ 📊 Excel  │
│                                                 │ 🖼️ Images │
│                                                 │ 📦 Raw    │
│                                                 └───────────┘
├─────────────────────────────────────────────────────────────┤
│ Key metrics                                                 │
│ ...                                                         │
└─────────────────────────────────────────────────────────────┘
```

---

## Report Template Preview

```
╔═══════════════════════════════════════════════════════════╗
║                    🚲 WHEELFLOW                            ║
║              CFD Simulation Report                         ║
╠═══════════════════════════════════════════════════════════╣
║                                                            ║
║  Simulation: TTTR28_22_TSV3                               ║
║  Date: January 23, 2025                                   ║
║  Quality: Standard (~2M cells)                            ║
║                                                            ║
╠═══════════════════════════════════════════════════════════╣
║  KEY RESULTS                                               ║
║  ─────────────────────────────────────────────────────    ║
║  Yaw    │  Fd (N)  │  Cd    │  CdA (m²)                   ║
║  0°     │  0.85    │  0.045 │  0.0070                     ║
║  5°     │  0.89    │  0.047 │  0.0074                     ║
║  10°    │  0.93    │  0.051 │  0.0079                     ║
║  15°    │  0.95    │  0.055 │  0.0086                     ║
║                                                            ║
╠═══════════════════════════════════════════════════════════╣
║  [Pressure Coefficient Visualization]                      ║
║                                                            ║
║  [Force Distribution Graph]                                ║
║                                                            ║
╠═══════════════════════════════════════════════════════════╣
║  Generated by WheelFlow v0.1                              ║
║  OpenFOAM CFD for Bicycle Wheels                          ║
╚═══════════════════════════════════════════════════════════╝
```

---

## Definition of Done
- [ ] PDF report generates correctly
- [ ] Excel export contains all data
- [ ] Image export works for all visualizations
- [ ] Download triggers browser download
- [ ] File naming is automatic and meaningful
- [ ] Unit tests pass for data formatting

---

## Estimated Effort
**Story Points**: 8

## Dependencies
- Results dashboard (US-001)
- Force distribution graph (US-003)
- Pressure slices (US-004)

## Technical Considerations
- PDF generation: Use library like jsPDF or puppeteer
- Excel generation: Use SheetJS or exceljs
- Image capture: Canvas toDataURL or html2canvas

