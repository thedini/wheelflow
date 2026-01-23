# Screenshot Reference Guide

This document describes the key screenshots captured during the analysis of WheelFlow and AeroCloud applications.

## How to View Screenshots

The screenshots referenced in user stories are captured from live browser sessions. To view current screenshots:

1. Open WheelFlow: https://containing-loving-donate-hats.trycloudflare.com/
2. Open AeroCloud: https://aerocloud.nablaflow.io/v7/simulations/15-tttr28-22-wakehalo-06aok2q4ttrl5703jc1m75jb5s

## Screenshot Descriptions

### AeroCloud Screenshots

| ID | Description | URL/View |
|----|-------------|----------|
| AC-01 | Results Dashboard - Key Metrics | Simulation results top section showing 3D preview, key metrics table with Force/Coefficient tabs, input parameters |
| AC-02 | Force Distribution Graph | Cumulative drag graph with position along model, Model toggle checkbox |
| AC-03 | Slices View | Pressure coefficient visualization with slice navigation, direction controls (X/Y/Z), field selector |
| AC-04 | Parts Breakdown | Horizontal bar chart showing drag force per component |
| AC-05 | Compare Runs | Table comparing multiple simulations with Yaw, Cd, heat transfer metrics |
| AC-06 | Project List | Projects overview with simulation counts, status badges |
| AC-07 | New Simulation Form | Simulation setup with Quality selector, Speed, Ground, Fluid, Yaw angles |

### WheelFlow Screenshots

| ID | Description | URL/View |
|----|-------------|----------|
| WF-01 | Main Upload View | Left panel with simulation parameters, right panel with 3D preview |
| WF-02 | Simulation Parameters | Full parameter list including Speed, Wheel Radius, Yaw Angles, Ground, Rotation, GPU, Mesh Quality |
| WF-03 | Empty Simulations Tab | "No simulations yet" empty state |
| WF-04 | Empty Results Tab | "No results to display" empty state |

## Key Visual Differences

### Navigation
- **AeroCloud**: Sidebar navigation + breadcrumbs (Projects > Master Testing > Simulation)
- **WheelFlow**: Top tab buttons (Upload | Simulations | Results) - currently not functional

### Color Scheme
- **AeroCloud**: Light theme, yellow/green accents, professional enterprise look
- **WheelFlow**: Dark theme, blue accents, modern developer look

### Data Display
- **AeroCloud**: Rich data visualization with graphs, slices, 3D views, comparison tables
- **WheelFlow**: Currently only input form, no results display

