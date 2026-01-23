# WheelFlow Bugs and UX Issues

## Overview
This document catalogs observed bugs, UX issues, and improvement opportunities in the WheelFlow application based on analysis conducted on January 23, 2026.

---

## Critical Bugs

### BUG-001: Navigation Tabs Don't Change View
**Severity**: HIGH
**Status**: OPEN

**Description**:
The navigation tabs (Upload, Simulations, Results) in the header don't appear to change the visible content or scroll to the respective sections.

**Steps to Reproduce**:
1. Load WheelFlow application
2. Click on "Simulations" tab
3. Observe: View remains the same
4. Click on "Results" tab
5. Observe: View remains the same

**Expected Behavior**:
Clicking navigation tabs should either:
- Switch to a different view/panel, OR
- Smooth scroll to the corresponding section

**Actual Behavior**:
Tabs highlight when clicked but no view change occurs. The three regions (Upload, Simulations, Results) exist in the DOM but aren't visible simultaneously or navigable.

**Screenshot Reference**:
Tab shows "Results" highlighted but Upload form is still visible.

**Suggested Fix**:
```javascript
// Option 1: Tab-based switching
const [activeTab, setActiveTab] = useState('upload');

// Option 2: Scroll to section
const scrollToSection = (sectionId) => {
  document.getElementById(sectionId)?.scrollIntoView({
    behavior: 'smooth'
  });
};
```

---

### BUG-002: Run Simulation Button Disabled State Not Clear
**Severity**: MEDIUM
**Status**: OPEN

**Description**:
The "Run Simulation" button shows a warning tooltip "⚠ Upload a geometry file first" but the visual disabled state is not immediately obvious.

**Expected Behavior**:
Button should be visually grayed out/disabled with clear indication.

**Suggested Fix**:
- Add `opacity: 0.5` and `cursor: not-allowed` to disabled button
- Show warning icon next to button, not just on hover

---

## UX Improvements

### UX-001: Empty States Need Better Messaging
**Priority**: MEDIUM

**Current State**:
"No simulations yet" message is visible but could be more actionable.

**Recommended Improvement**:
- Add an illustration/icon
- Include step-by-step getting started guide
- Add sample STL download link for testing
- Show estimated time for first simulation

**Example**:
```
┌────────────────────────────────────────┐
│     [🚲 Illustration]                  │
│                                        │
│   No simulations yet                   │
│                                        │
│   Get started in 3 steps:              │
│   1. Upload your wheel geometry (STL)  │
│   2. Configure simulation parameters   │
│   3. Click "Run Simulation"            │
│                                        │
│   [📥 Download sample wheel STL]       │
│   [▶️ Watch tutorial video]            │
└────────────────────────────────────────┘
```

---

### UX-002: Speed Unit Display Enhancement
**Priority**: LOW

**Current State**:
Speed shows "≈ 50 km/h / 31 mph" below the input field.

**Recommended Improvement**:
- Real-time update as user types
- Add unit toggle (m/s / km/h / mph)
- Show typical racing speeds for reference

---

### UX-003: Yaw Angles Input UX
**Priority**: MEDIUM

**Current State**:
Comma-separated text input "0, 5, 10, 15, 20"

**Issues**:
- No validation feedback
- Easy to make formatting errors
- Not clear what units are used

**Recommended Improvement**:
- Add individual angle inputs with +/- buttons (like AeroCloud)
- Include degree symbol (°)
- Add common presets: "Standard sweep (0-20°)", "High yaw (15-25°)"
- Real-time validation with error highlighting

---

### UX-004: 3D Preview Controls Discoverability
**Priority**: MEDIUM

**Current State**:
Reset view and Toggle wireframe buttons are small icons in corner.

**Recommended Improvement**:
- Add tooltips on hover
- Consider floating control panel
- Add keyboard shortcuts (R for reset, W for wireframe)
- Show orbit/pan/zoom instructions on first use

---

### UX-005: Progress/Status Feedback Missing
**Priority**: HIGH

**Current State**:
No visible indication of simulation progress.

**Recommended Features**:
- Progress bar during simulation
- Estimated time remaining
- Current stage indicator (Meshing → Solving → Post-processing)
- Real-time residual plot (advanced)
- Notification when complete

---

### UX-006: Responsive Design Concerns
**Priority**: MEDIUM

**Current State**:
Two-column layout may not work well on smaller screens.

**Recommended Testing**:
- Test on 1024px width
- Test on tablet (768px)
- Consider mobile experience (or show "Desktop recommended" message)

---

## Accessibility Issues

### A11Y-001: Color Contrast
**Priority**: MEDIUM

**Current State**:
Dark theme with blue on dark gray may have contrast issues.

**Recommended**:
- Verify WCAG 2.1 AA compliance (4.5:1 ratio for text)
- Test with color blindness simulators
- Ensure focus states are visible

---

### A11Y-002: Screen Reader Support
**Priority**: MEDIUM

**Current State**:
Unknown - needs testing.

**Recommended**:
- Add proper ARIA labels
- Ensure form inputs have associated labels
- Test with VoiceOver/NVDA

---

### A11Y-003: Keyboard Navigation
**Priority**: MEDIUM

**Current State**:
Unknown - needs testing.

**Recommended**:
- Ensure all interactive elements are focusable
- Visible focus indicators
- Logical tab order
- Escape key to close modals/dropdowns

---

## Performance Observations

### PERF-001: 3D Preview Loading
**Priority**: LOW

**Observation**:
3D preview shows "Upload a model to preview" placeholder. Need to verify loading states and performance with large STL files.

**Recommendations**:
- Add file size limits with clear messaging
- Show loading spinner during model parsing
- Display triangle count warning if too high
- Consider progressive loading for large models

---

## Missing Error Handling

### ERR-001: Upload Error States
**Priority**: HIGH

**Current State**:
Unknown behavior for invalid file uploads.

**Needed**:
- Invalid file format error
- File too large error
- Corrupted/malformed STL error
- Network error handling (for future cloud features)

---

### ERR-002: Simulation Failure States
**Priority**: HIGH

**Current State**:
Unknown behavior when simulation fails.

**Needed**:
- Clear error message with cause
- Suggested fixes
- Option to retry
- Log access for debugging

---

## Comparison with AeroCloud Polish

### Visual Polish Items
| Item | AeroCloud | WheelFlow | Gap |
|------|-----------|-----------|-----|
| Consistent spacing | ✅ | Needs review | Medium |
| Badge styling | ✅ Professional | ❌ Missing | High |
| Status indicators | ✅ Green dots, badges | ❌ Missing | High |
| Loading states | ✅ Skeleton screens | ❓ Unknown | Medium |
| Tooltips | ✅ Help icons (?) | ⚠️ Limited | Medium |
| Breadcrumbs | ✅ Full navigation | ❌ Missing | Medium |

---

## Recommended Priorities

### Immediate (Before Beta)
1. Fix navigation tabs (BUG-001)
2. Add simulation progress indicator (UX-005)
3. Implement basic error handling (ERR-001, ERR-002)
4. Add results display (see User Stories)

### Short-term (Beta)
1. Improve empty states (UX-001)
2. Add status badges and indicators
3. Keyboard navigation support
4. Basic accessibility fixes

### Medium-term (v1.0)
1. Responsive design improvements
2. Advanced accessibility compliance
3. Full keyboard shortcuts
4. Help documentation integration

