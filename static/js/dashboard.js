/**
 * WheelFlow F1-Style Dashboard
 * Real-time CFD telemetry visualization
 */

let currentJobId = null;
let convergenceChart = null;
let polarChart = null;
let updateInterval = null;
let systemInterval = null;
let startTime = null;
let elapsedInterval = null;

// 3D Viewer variables
let scene3d, camera3d, renderer3d, controls3d, wheelMesh;
let viewer3dInitialized = false;

// Initialize dashboard
function initDashboard(jobId) {
    // Always initialize UI components first
    initConvergenceChart();
    initPolarChart();
    initPartsBreakdownChart();
    init3DViewer();
    initViewButtons();
    initSpeedometer();

    // Start elapsed timer display (shows 00:00:00 until job starts)
    if (!elapsedInterval) {
        elapsedInterval = setInterval(updateElapsedTime, 1000);
    }

    // Start system stats polling
    if (!systemInterval) {
        systemInterval = setInterval(updateSystemStats, 1000);
        updateSystemStats(); // Initial call
    }

    if (!jobId || jobId === '{{ job_id }}' || jobId === '') {
        // No job ID provided - show list of jobs or prompt
        showJobSelector();
        return;
    }

    currentJobId = jobId;
    startTime = Date.now();

    // Start polling for updates
    if (updateInterval) clearInterval(updateInterval);
    updateInterval = setInterval(updateDashboard, 2000);

    // Initial update
    updateDashboard();

    console.log('Dashboard initialized for job:', jobId);
}

// Show job selector when no job ID is provided
async function showJobSelector() {
    // Show initial "waiting" state
    document.getElementById('session-name').textContent = 'WAITING FOR SIMULATION';
    document.getElementById('session-status').textContent = 'STANDBY';
    document.querySelector('.status-dot').classList.remove('live');
    document.querySelector('.status-dot').style.background = '#8b98a5';

    // Show placeholder message in charts
    showChartPlaceholder('convergence-chart', 'Waiting for simulation data...');

    try {
        const response = await fetch('/api/jobs');
        const jobs = await response.json();

        if (jobs.length === 0) {
            document.getElementById('session-name').textContent = 'NO SIMULATIONS';
            document.getElementById('session-status').textContent = 'IDLE';
            showViewerMessage('No simulation data available. Start a simulation from the Upload page.');
            return;
        }

        // Use the most recent job
        const latestJob = jobs.sort((a, b) =>
            new Date(b.created_at) - new Date(a.created_at)
        )[0];

        console.log('Auto-selecting latest job:', latestJob.id);

        // Re-initialize with the job
        currentJobId = latestJob.id;
        startTime = new Date(latestJob.created_at).getTime();

        // Start polling
        if (updateInterval) clearInterval(updateInterval);
        updateInterval = setInterval(updateDashboard, 2000);
        updateDashboard();

        // Update status indicator
        document.querySelector('.status-dot').classList.add('live');
        document.querySelector('.status-dot').style.background = '';
        document.getElementById('session-status').textContent = 'LIVE';

    } catch (error) {
        console.error('Failed to fetch jobs:', error);
        document.getElementById('session-name').textContent = 'CONNECTION ERROR';
        document.getElementById('session-status').textContent = 'OFFLINE';
        showViewerMessage('Cannot connect to server', 'error');
    }
}

// Show placeholder message in chart area
function showChartPlaceholder(chartId, message) {
    const canvas = document.getElementById(chartId);
    if (!canvas) return;

    const container = canvas.parentElement;
    let placeholder = container.querySelector('.chart-placeholder');

    if (!placeholder) {
        placeholder = document.createElement('div');
        placeholder.className = 'chart-placeholder';
        placeholder.style.cssText = `
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: #606070;
            font-size: 12px;
            text-align: center;
            pointer-events: none;
        `;
        container.style.position = 'relative';
        container.appendChild(placeholder);
    }

    placeholder.textContent = message;
    placeholder.style.display = 'block';
}

// Hide chart placeholder
function hideChartPlaceholder(chartId) {
    const canvas = document.getElementById(chartId);
    if (!canvas) return;

    const placeholder = canvas.parentElement.querySelector('.chart-placeholder');
    if (placeholder) {
        placeholder.style.display = 'none';
    }
}

// Update system statistics (CPU, RAM, GPU)
async function updateSystemStats() {
    try {
        const response = await fetch('/api/system/stats');
        if (!response.ok) return;

        const stats = await response.json();
        updateTachometers(stats);
        updateOpenFOAMStatus(stats);

    } catch (error) {
        console.error('System stats error:', error);
    }
}

// Update tachometer gauges
function updateTachometers(stats) {
    // CPU Tachometer
    const cpuPercent = stats.cpu?.percent || 0;
    updateTachometer('cpu', cpuPercent);
    document.getElementById('cpu-value').textContent = `${Math.round(cpuPercent)}%`;

    // Memory Tachometer
    const memPercent = stats.memory?.percent || 0;
    updateTachometer('mem', memPercent);
    const memUsed = stats.memory?.used_gb || 0;
    document.getElementById('mem-value').textContent = `${memUsed.toFixed(1)}G`;

    // GPU Tachometer
    if (stats.gpu?.available && stats.gpu.devices?.length > 0) {
        const gpu = stats.gpu.devices[0];
        const gpuPercent = gpu.utilization_percent || 0;
        updateTachometer('gpu', gpuPercent);
        document.getElementById('gpu-value').textContent = `${Math.round(gpuPercent)}%`;
        document.getElementById('gpu-tach').classList.remove('inactive');
    } else {
        document.getElementById('gpu-value').textContent = 'N/A';
        document.getElementById('gpu-tach').classList.add('inactive');
    }

    // Cache (from memory stats)
    const cachedGb = stats.memory?.cached_gb || 0;
    const totalGb = stats.memory?.total_gb || 1;
    const cachePercent = (cachedGb / totalGb) * 100;
    document.getElementById('cache-usage').style.width = `${cachePercent}%`;
    document.getElementById('cache-value').textContent = `${cachedGb.toFixed(1)}G`;

    // Disk
    const diskPercent = stats.disk?.percent || 0;
    document.getElementById('disk-usage').style.width = `${diskPercent}%`;
    document.getElementById('disk-value').textContent = `${Math.round(diskPercent)}%`;
}

// Update a single tachometer gauge
function updateTachometer(id, percent) {
    // Update arc fill (stroke-dashoffset)
    const fillEl = document.getElementById(`${id}-tach-fill`);
    if (fillEl) {
        // Arc length is 126, so offset = 126 - (percent/100 * 126)
        const offset = 126 - (percent / 100 * 126);
        fillEl.style.strokeDashoffset = offset;
    }

    // Update needle rotation (-90° to +90° range)
    const needleEl = document.getElementById(`${id}-needle`);
    if (needleEl) {
        // Needle: -90° at 0%, +90° at 100%
        const angle = -90 + (percent / 100 * 180);
        needleEl.style.transform = `rotate(${angle}deg)`;
    }
}

// Update OpenFOAM process status
function updateOpenFOAMStatus(stats) {
    const ofStats = stats.openfoam || {};
    const statusDot = document.getElementById('of-status-dot');
    const solverEl = document.getElementById('solver-name');

    // Update active solver
    if (ofStats.active_solver) {
        solverEl.textContent = ofStats.active_solver.toUpperCase();
        statusDot.className = 'of-dot';

        if (ofStats.active_solver.includes('Mesh')) {
            statusDot.classList.add('meshing');
        } else if (ofStats.active_solver.includes('Foam')) {
            statusDot.classList.add('solving');
        } else {
            statusDot.classList.add('running');
        }
    } else if (ofStats.processes?.length > 0) {
        solverEl.textContent = 'RUNNING';
        statusDot.className = 'of-dot running';
    } else {
        solverEl.textContent = 'IDLE';
        statusDot.className = 'of-dot';
    }

    // Update MPI ranks
    document.getElementById('mpi-ranks').textContent = ofStats.mpi_ranks || 1;
}

// Update elapsed time display
function updateElapsedTime() {
    if (!startTime) return;

    const elapsed = Date.now() - startTime;
    const hours = Math.floor(elapsed / 3600000);
    const minutes = Math.floor((elapsed % 3600000) / 60000);
    const seconds = Math.floor((elapsed % 60000) / 1000);

    const timeStr = [
        hours.toString().padStart(2, '0'),
        minutes.toString().padStart(2, '0'),
        seconds.toString().padStart(2, '0')
    ].join(':');

    document.getElementById('elapsed-time').textContent = timeStr;
}

// Main update function
async function updateDashboard() {
    if (!currentJobId) return;

    try {
        const response = await fetch(`/api/jobs/${currentJobId}`);
        if (!response.ok) throw new Error('Failed to fetch job');

        const job = await response.json();
        updateJobStatus(job);
        updateMetrics(job);
        updateComparison(job);

        // If job is complete, stop polling
        if (job.status === 'complete' || job.status === 'failed') {
            clearInterval(updateInterval);
            updateInterval = null;

            if (job.status === 'complete') {
                document.getElementById('session-status').textContent = 'COMPLETE';
                document.querySelector('.status-dot').classList.remove('live');
                document.querySelector('.status-dot').style.background = '#00d26a';
            } else {
                document.getElementById('session-status').textContent = 'FAILED';
                document.querySelector('.status-dot').style.background = '#e10600';
            }
        }

    } catch (error) {
        console.error('Dashboard update error:', error);
    }
}

// Update job status and progress
function updateJobStatus(job) {
    const progress = job.progress || 0;

    // Update progress bar
    document.getElementById('progress-fill').style.width = `${progress}%`;
    document.getElementById('progress-percent').textContent = `${progress}%`;

    // Update stages
    const stages = ['upload', 'mesh', 'solve', 'post'];
    const stageMap = {
        'queued': 0,
        'preparing': 0,
        'meshing': 1,
        'solving': 2,
        'post-processing': 3,
        'complete': 4
    };

    const currentStage = stageMap[job.status] || 0;

    stages.forEach((stage, index) => {
        const el = document.querySelector(`[data-stage="${stage}"]`);
        if (el) {
            el.classList.remove('completed', 'active');
            if (index < currentStage) {
                el.classList.add('completed');
            } else if (index === currentStage) {
                el.classList.add('active');
            }
        }
    });

    // Update session name
    document.getElementById('session-name').textContent =
        `${job.name || 'SIMULATION'} - ${(job.config?.quality || 'STANDARD').toUpperCase()}`;

    // Update solver info
    document.getElementById('solver-name').textContent =
        job.status === 'solving' ? 'simpleFoam' : job.status.toUpperCase();

    // Update mesh stats from config
    if (job.config) {
        const qualityCells = {
            'basic': '~500K',
            'standard': '~2M',
            'pro': '~8M'
        };
        document.getElementById('cell-count').textContent =
            qualityCells[job.config.quality] || '--';
        document.getElementById('quality-level').textContent =
            (job.config.quality || 'standard').toUpperCase();

        // Update speed display
        const speed = job.config.speed || 13.9;
        const speedKmh = Math.round(speed * 3.6);
        document.getElementById('speed-value').textContent = speedKmh;
        document.getElementById('velocity-ms').textContent = `${speed.toFixed(1)} m/s`;
        document.getElementById('yaw-angle').textContent = `${job.config.yaw_angles?.[0] || 0}°`;

        // Update speedometer visualization
        updateSpeedometer(speedKmh);

        // Update Reynolds number
        const re = job.config.reynolds || 0;
        document.getElementById('re-value').textContent = re > 0 ? formatNumber(re, 0) : '--';
    }

    // Set start time from job creation if not set
    if (!startTime && job.created_at) {
        startTime = new Date(job.created_at).getTime();
    }

    // Try to load pressure surface when simulation advances
    if (job.status === 'post-processing' || job.status === 'complete') {
        loadPressureSurface(currentJobId);
        loadPartsBreakdown(currentJobId);
    }

    // Load hero image when simulation completes
    if (job.status === 'complete') {
        loadHeroImage(currentJobId);
    }
}

// Update metrics display
function updateMetrics(job) {
    if (!job.results) return;

    const results = job.results;
    const coefficients = results.coefficients || {};

    // Update coefficients
    const Cd = coefficients.Cd || 0;
    const Cl = coefficients.Cl || 0;
    const Cm = coefficients.Cm || 0;

    document.getElementById('cd-value').textContent = Cd.toFixed(4);
    document.getElementById('cl-value').textContent = Cl.toFixed(4);
    document.getElementById('cm-value').textContent = Cm.toFixed(4);

    // Use forces from results if available, otherwise calculate
    let dragN, liftN, CdA;

    if (results.forces && results.CdA) {
        // Use pre-calculated values from backend
        dragN = results.forces.drag_N;
        liftN = results.forces.lift_N;
        CdA = results.CdA_cm2 || results.CdA * 10000; // Backend may provide cm² directly
    } else {
        // Fallback calculation
        const rho = 1.225;
        const U = job.config?.speed || 13.9;
        const Aref = job.config?.aref || results.aref || 0.0225; // Use actual Aref from config/results
        const q = 0.5 * rho * U * U;

        dragN = Cd * q * Aref;
        liftN = Cl * q * Aref;
        CdA = Cd * Aref * 10000; // cm²
    }

    // Update primary metric (CdA)
    document.getElementById('cda-value').textContent = CdA.toFixed(1);
    document.getElementById('cda-gauge').style.width = `${Math.min(CdA / 200 * 100, 100)}%`;

    // Calculate delta vs reference (110 cm² target)
    const targetCdA = 110;
    const deltaCdA = CdA - targetCdA;
    const deltaPercent = (deltaCdA / targetCdA * 100).toFixed(1);

    const deltaEl = document.getElementById('cda-delta');
    if (deltaCdA > 0) {
        deltaEl.querySelector('.delta-arrow').textContent = '▲';
        deltaEl.querySelector('.delta-arrow').classList.add('up');
        deltaEl.querySelector('.delta-value').textContent = `+${deltaPercent}%`;
        deltaEl.querySelector('.delta-value').style.color = '#e10600';
    } else {
        deltaEl.querySelector('.delta-arrow').textContent = '▼';
        deltaEl.querySelector('.delta-arrow').classList.remove('up');
        deltaEl.querySelector('.delta-value').textContent = `${deltaPercent}%`;
        deltaEl.querySelector('.delta-value').style.color = '#00d26a';
    }

    // Update secondary metrics
    document.getElementById('drag-value').textContent = dragN.toFixed(2);
    document.getElementById('lift-value').textContent = liftN.toFixed(2);

    // Update iterations
    document.getElementById('iterations').textContent =
        Math.round(coefficients.time || results.iteration || 0);

    // Update residual (simulated for now)
    document.getElementById('residual-value').textContent = '1.0e-4';

    // Update convergence chart
    updateConvergenceChart(job);

    // Update yaw sweep polar chart (if this is part of a batch)
    loadYawSweepData(job.id);

    // Load visualization data when complete
    if (job.status === 'complete') {
        loadPressureSurface(job.id);
        loadAvailableSlices();
    }
}

// Update comparison table
function updateComparison(job) {
    if (!job.results?.coefficients) return;

    const Cd = job.results.coefficients.Cd || 0;

    // Reference values (AeroCloud at 15° yaw)
    const refDrag = 1.31;
    const refCdA = 110; // cm²
    const refCd = 0.490;

    // Calculate current values
    const rho = 1.225;
    const U = job.config?.speed || 13.9;
    const Aref = 0.0225;
    const q = 0.5 * rho * U * U;

    const dragN = Cd * q * Aref;
    const CdA = Cd * Aref * 10000;

    // Update table rows
    updateCompRow('comp-drag', dragN, refDrag);
    updateCompRow('comp-cda', CdA, refCdA);
    updateCompRow('comp-cd', Cd, refCd);

    // Update note about yaw angle
    const currentYaw = job.config?.yaw_angles?.[0] || 0;
    if (currentYaw !== 15) {
        document.getElementById('comparison-note').textContent =
            `Current: ${currentYaw}° yaw, Reference: 15° yaw`;
    }
}

function updateCompRow(rowId, current, target) {
    const row = document.getElementById(rowId);
    if (!row) return;

    const currentEl = row.querySelector('.current');
    const diffEl = row.querySelector('.diff');

    currentEl.textContent = current.toFixed(current < 10 ? 3 : 1);

    const diffPercent = ((current - target) / target * 100).toFixed(1);
    diffEl.textContent = `${diffPercent > 0 ? '+' : ''}${diffPercent}%`;
    diffEl.className = 'diff ' + (diffPercent > 0 ? 'positive' : 'negative');
}

// Initialize convergence chart
function initConvergenceChart() {
    const ctx = document.getElementById('convergence-chart');
    if (!ctx) return;

    convergenceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Cd',
                data: [],
                borderColor: '#0090ff',
                backgroundColor: 'rgba(0, 144, 255, 0.1)',
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Iteration',
                        color: '#606070',
                        font: { size: 10 }
                    },
                    grid: {
                        color: '#2a2a3a'
                    },
                    ticks: {
                        color: '#606070',
                        font: { size: 9 }
                    }
                },
                y: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Cd',
                        color: '#606070',
                        font: { size: 10 }
                    },
                    grid: {
                        color: '#2a2a3a'
                    },
                    ticks: {
                        color: '#606070',
                        font: { size: 9 }
                    }
                }
            }
        }
    });
}

// Update convergence chart with real data from API
async function updateConvergenceChart(job) {
    if (!convergenceChart) return;

    try {
        // Fetch real convergence data
        const response = await fetch(`/api/jobs/${currentJobId}/convergence`);
        if (response.ok) {
            const data = await response.json();

            if (data.time && data.time.length > 0) {
                // Hide placeholder
                hideChartPlaceholder('convergence-chart');

                // Sample data for performance (max 500 points)
                let times = data.time;
                let cdValues = data.Cd;
                const maxPoints = 500;

                if (times.length > maxPoints) {
                    const step = Math.ceil(times.length / maxPoints);
                    const sampledTimes = [];
                    const sampledCd = [];

                    for (let i = 0; i < times.length; i += step) {
                        sampledTimes.push(times[i]);
                        sampledCd.push(cdValues[i]);
                    }

                    // Always include the last point
                    if (sampledTimes[sampledTimes.length - 1] !== times[times.length - 1]) {
                        sampledTimes.push(times[times.length - 1]);
                        sampledCd.push(cdValues[cdValues.length - 1]);
                    }

                    times = sampledTimes;
                    cdValues = sampledCd;
                }

                // Use real data
                convergenceChart.data.labels = times;
                convergenceChart.data.datasets[0].data = cdValues;
                convergenceChart.update('none');

                // Update iteration count (show total, not sampled)
                document.getElementById('iterations').textContent = data.time.length;
                document.getElementById('of-iteration').textContent = data.time.length;

                // Update final Cd value in the metrics
                if (data.Cd && data.Cd.length > 0) {
                    const finalCd = data.Cd[data.Cd.length - 1];
                    const cdElement = document.getElementById('cd-value');
                    if (cdElement) {
                        cdElement.textContent = finalCd.toFixed(4);
                    }
                }

                // Update final Cl value if available
                if (data.Cl && data.Cl.length > 0) {
                    const finalCl = data.Cl[data.Cl.length - 1];
                    const clElement = document.getElementById('cl-value');
                    if (clElement) {
                        clElement.textContent = finalCl.toFixed(4);
                    }
                }

                // Update final Cm value if available
                if (data.Cm && data.Cm.length > 0) {
                    const finalCm = data.Cm[data.Cm.length - 1];
                    const cmElement = document.getElementById('cm-value');
                    if (cmElement) {
                        cmElement.textContent = finalCm.toFixed(4);
                    }
                }

                return; // Successfully loaded real data, skip fallback
            }
        }
    } catch (error) {
        console.log('Convergence API error:', error);
    }

    // Only show placeholder when no real data is available
    // Don't generate fake simulated data
    if (!job || job.status === 'queued' || job.progress === 0) {
        showChartPlaceholder('convergence-chart', 'Waiting for convergence data...');
    }
}

// Initialize polar chart for yaw sweep
function initPolarChart() {
    const ctx = document.getElementById('yaw-polar-chart');
    if (!ctx) return;

    polarChart = new Chart(ctx, {
        type: 'radar',
        data: {
            labels: ['0°', '5°', '10°', '15°', '20°'],
            datasets: [{
                label: 'Cd',
                data: [0.15, 0.18, 0.25, 0.35, 0.45],
                borderColor: '#e10600',
                backgroundColor: 'rgba(225, 6, 0, 0.2)',
                pointBackgroundColor: '#e10600',
                pointBorderColor: '#fff',
                pointRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                r: {
                    beginAtZero: true,
                    grid: {
                        color: '#2a2a3a'
                    },
                    angleLines: {
                        color: '#2a2a3a'
                    },
                    pointLabels: {
                        color: '#a0a0b0',
                        font: { size: 10 }
                    },
                    ticks: {
                        color: '#606070',
                        font: { size: 8 },
                        backdropColor: 'transparent'
                    }
                }
            }
        }
    });
}

// Load yaw sweep data for polar chart
async function loadYawSweepData(jobId) {
    if (!polarChart || !jobId) return;

    // Extract batch prefix from job ID (e.g., "7a430d2b_00" -> "7a430d2b")
    const parts = jobId.split('_');
    if (parts.length < 2) {
        console.log('Job ID does not appear to be part of a yaw sweep batch');
        return;
    }

    const batchPrefix = parts.slice(0, -1).join('_');

    try {
        const response = await fetch(`/api/yaw_sweep/${batchPrefix}`);
        if (!response.ok) {
            console.log('Yaw sweep data not available');
            return;
        }

        const data = await response.json();

        if (data.results && data.results.length > 0) {
            // Extract Cd values for each angle
            const cdValues = data.results.map(r => r.Cd);
            const clValues = data.results.map(r => r.Cl);

            // Check if we have at least some valid data
            const validCdCount = cdValues.filter(v => v !== null).length;
            if (validCdCount === 0) {
                console.log('No valid Cd values in yaw sweep');
                return;
            }

            // Update polar chart with real data
            polarChart.data.datasets[0].data = cdValues.map(v => v !== null ? v : 0);
            polarChart.data.datasets[0].label = 'Cd';

            // Add Cl dataset if we have Cl data
            if (clValues.some(v => v !== null)) {
                if (polarChart.data.datasets.length < 2) {
                    polarChart.data.datasets.push({
                        label: 'Cl',
                        data: clValues.map(v => v !== null ? v : 0),
                        borderColor: '#1d9bf0',
                        backgroundColor: 'rgba(29, 155, 240, 0.2)',
                        pointBackgroundColor: '#1d9bf0',
                        pointBorderColor: '#fff',
                        pointRadius: 4
                    });
                } else {
                    polarChart.data.datasets[1].data = clValues.map(v => v !== null ? v : 0);
                }
            }

            polarChart.update('none');

            // Update yaw sweep status indicator
            const sweepStatus = document.getElementById('yaw-sweep-status');
            if (sweepStatus) {
                sweepStatus.textContent = data.complete ?
                    `${validCdCount}/5 angles complete` :
                    `${validCdCount}/5 angles running`;
            }

            console.log('Yaw sweep data loaded:', data.results);
        }
    } catch (error) {
        console.log('Error loading yaw sweep data:', error);
    }
}

// Format numbers with K, M suffixes
function formatNumber(num, decimals = 1) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(decimals) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(decimals) + 'K';
    }
    return num.toFixed(decimals);
}

// Export Dropdown Toggle
function toggleExportMenu() {
    const dropdown = document.querySelector('.export-dropdown');
    dropdown.classList.toggle('open');
}

// Close export menu when clicking outside
document.addEventListener('click', (e) => {
    const dropdown = document.querySelector('.export-dropdown');
    if (dropdown && !dropdown.contains(e.target)) {
        dropdown.classList.remove('open');
    }
});

// PDF Report Generation
async function exportPDF() {
    if (!currentJobId) {
        alert('No simulation data available');
        return;
    }

    const dropdown = document.querySelector('.export-dropdown');
    dropdown.classList.remove('open');

    const btn = document.querySelector('.export-btn-main');
    btn.classList.add('loading');

    try {
        const response = await fetch(`/api/jobs/${currentJobId}`);
        const job = await response.json();

        // Initialize jsPDF
        const { jsPDF } = window.jspdf;
        const doc = new jsPDF({
            orientation: 'portrait',
            unit: 'mm',
            format: 'a4'
        });

        const pageWidth = doc.internal.pageSize.getWidth();
        const pageHeight = doc.internal.pageSize.getHeight();
        const margin = 15;

        // Colors matching WheelFlow dark theme
        const colors = {
            primary: [0, 144, 255],      // Accent blue
            secondary: [139, 152, 165],  // Text secondary
            dark: [15, 20, 25],          // Background
            text: [255, 255, 255],       // White text
            success: [0, 210, 106],      // Green
            warning: [255, 215, 0]       // Yellow
        };

        // === PAGE 1: COVER ===
        // Dark background
        doc.setFillColor(...colors.dark);
        doc.rect(0, 0, pageWidth, pageHeight, 'F');

        // Header accent bar
        doc.setFillColor(...colors.primary);
        doc.rect(0, 0, pageWidth, 3, 'F');

        // WheelFlow Logo Area
        doc.setFillColor(30, 35, 40);
        doc.roundedRect(margin, 30, pageWidth - 2*margin, 50, 3, 3, 'F');

        // Logo icon (wheel)
        doc.setDrawColor(...colors.primary);
        doc.setLineWidth(1.5);
        doc.circle(pageWidth/2, 55, 12);
        doc.circle(pageWidth/2, 55, 5);
        doc.line(pageWidth/2, 43, pageWidth/2, 49);
        doc.line(pageWidth/2, 61, pageWidth/2, 67);

        // Title
        doc.setTextColor(...colors.text);
        doc.setFontSize(28);
        doc.setFont('helvetica', 'bold');
        doc.text('WHEELFLOW', pageWidth/2, 95, { align: 'center' });

        doc.setFontSize(12);
        doc.setTextColor(...colors.secondary);
        doc.text('CFD SIMULATION REPORT', pageWidth/2, 105, { align: 'center' });

        // Simulation Name Card
        doc.setFillColor(25, 30, 35);
        doc.roundedRect(margin, 120, pageWidth - 2*margin, 45, 3, 3, 'F');

        doc.setTextColor(...colors.primary);
        doc.setFontSize(10);
        doc.text('SIMULATION', margin + 10, 133);

        doc.setTextColor(...colors.text);
        doc.setFontSize(20);
        doc.setFont('helvetica', 'bold');
        doc.text(job.name || 'Unnamed Simulation', margin + 10, 148);

        doc.setTextColor(...colors.secondary);
        doc.setFontSize(10);
        doc.setFont('helvetica', 'normal');
        const dateStr = new Date().toLocaleDateString('en-US', {
            year: 'numeric', month: 'long', day: 'numeric'
        });
        doc.text(`Generated: ${dateStr}`, margin + 10, 158);

        // Key Result Preview
        const results = job.results || {};
        const CdA = results.CdA ? (results.CdA * 10000).toFixed(1) : (results.CdA_cm2 || '--');

        doc.setFillColor(25, 30, 35);
        doc.roundedRect(margin, 175, pageWidth - 2*margin, 50, 3, 3, 'F');

        doc.setTextColor(...colors.primary);
        doc.setFontSize(10);
        doc.text('PRIMARY RESULT', margin + 10, 188);

        doc.setTextColor(...colors.text);
        doc.setFontSize(36);
        doc.setFont('helvetica', 'bold');
        doc.text(`${CdA}`, margin + 10, 212);

        doc.setFontSize(14);
        doc.setTextColor(...colors.secondary);
        doc.text('cm²  CdA', margin + 55, 212);

        // Quality Badge
        const quality = (job.config?.quality || 'standard').toUpperCase();
        doc.setFillColor(...colors.primary);
        doc.roundedRect(pageWidth - margin - 45, 195, 35, 18, 2, 2, 'F');
        doc.setTextColor(...colors.text);
        doc.setFontSize(9);
        doc.setFont('helvetica', 'bold');
        doc.text(quality, pageWidth - margin - 27.5, 206, { align: 'center' });

        // Footer
        doc.setTextColor(...colors.secondary);
        doc.setFontSize(8);
        doc.setFont('helvetica', 'normal');
        doc.text('Powered by OpenFOAM | Local CFD Analysis', pageWidth/2, pageHeight - 15, { align: 'center' });

        // === PAGE 2: RESULTS SUMMARY ===
        doc.addPage();

        // Header
        doc.setFillColor(...colors.dark);
        doc.rect(0, 0, pageWidth, pageHeight, 'F');
        doc.setFillColor(...colors.primary);
        doc.rect(0, 0, pageWidth, 3, 'F');

        doc.setTextColor(...colors.text);
        doc.setFontSize(16);
        doc.setFont('helvetica', 'bold');
        doc.text('RESULTS SUMMARY', margin, 20);

        // Simulation Parameters Section
        doc.setFillColor(25, 30, 35);
        doc.roundedRect(margin, 28, pageWidth - 2*margin, 55, 3, 3, 'F');

        doc.setTextColor(...colors.primary);
        doc.setFontSize(10);
        doc.text('INPUT PARAMETERS', margin + 8, 40);

        const config = job.config || {};
        const params = [
            ['Speed', `${config.speed || 13.9} m/s (${Math.round((config.speed || 13.9) * 3.6)} km/h)`],
            ['Yaw Angle', `${config.yaw_angles?.[0] || 0}°`],
            ['Mesh Quality', (config.quality || 'standard').toUpperCase()],
            ['Ground', config.ground_enabled !== false ? `${config.ground_type || 'moving'} belt` : 'Disabled'],
            ['Wheel Rotation', config.rolling_enabled ? 'Enabled (MRF)' : 'Disabled'],
            ['Wheel Radius', `${config.wheel_radius || 0.325} m`]
        ];

        doc.setFontSize(9);
        doc.setFont('helvetica', 'normal');
        let yPos = 50;
        params.forEach(([label, value], i) => {
            const col = i < 3 ? 0 : 1;
            const row = i % 3;
            const xBase = margin + 8 + col * 85;
            const y = 50 + row * 10;

            doc.setTextColor(...colors.secondary);
            doc.text(label + ':', xBase, y);
            doc.setTextColor(...colors.text);
            doc.text(value, xBase + 40, y);
        });

        // Key Metrics Table
        doc.setTextColor(...colors.primary);
        doc.setFontSize(10);
        doc.setFont('helvetica', 'bold');
        doc.text('KEY METRICS', margin + 8, 95);

        const coefficients = results.coefficients || {};
        const forces = results.forces || {};

        // Calculate forces if not provided
        const rho = 1.225;
        const U = config.speed || 13.9;
        const Aref = config.aref || results.aref || 0.0225;
        const q = 0.5 * rho * U * U;

        const Cd = coefficients.Cd || 0;
        const Cl = coefficients.Cl || 0;
        const Cm = coefficients.Cm || 0;
        const dragN = forces.drag_N || (Cd * q * Aref);
        const liftN = forces.lift_N || (Cl * q * Aref);
        const CdAval = results.CdA ? results.CdA * 10000 : (Cd * Aref * 10000);

        // Metrics table using autoTable
        doc.autoTable({
            startY: 100,
            head: [['Metric', 'Value', 'Unit', 'Description']],
            body: [
                ['Drag Force (Fd)', dragN.toFixed(3), 'N', 'Aerodynamic drag'],
                ['Lift Force (Fl)', liftN.toFixed(3), 'N', 'Vertical force'],
                ['Drag Coefficient (Cd)', Cd.toFixed(4), '-', 'Dimensionless drag'],
                ['Lift Coefficient (Cl)', Cl.toFixed(4), '-', 'Dimensionless lift'],
                ['Moment Coefficient (Cm)', Cm.toFixed(4), '-', 'Pitching moment'],
                ['CdA (Drag Area)', CdAval.toFixed(1), 'cm²', 'Cd × Reference Area'],
            ],
            theme: 'plain',
            styles: {
                fillColor: [25, 30, 35],
                textColor: [255, 255, 255],
                fontSize: 9,
                cellPadding: 4
            },
            headStyles: {
                fillColor: [0, 144, 255],
                textColor: [255, 255, 255],
                fontStyle: 'bold',
                fontSize: 9
            },
            alternateRowStyles: {
                fillColor: [30, 35, 40]
            },
            margin: { left: margin, right: margin }
        });

        // Comparison with Reference (if available)
        if (results.aerocloud_comparison) {
            const comp = results.aerocloud_comparison;
            const lastY = doc.lastAutoTable.finalY + 15;

            doc.setTextColor(...colors.primary);
            doc.setFontSize(10);
            doc.setFont('helvetica', 'bold');
            doc.text('REFERENCE COMPARISON', margin + 8, lastY);

            doc.autoTable({
                startY: lastY + 5,
                head: [['Metric', 'Current', 'AeroCloud Ref', 'Difference']],
                body: [
                    ['Drag (N)', dragN.toFixed(2), '1.31', `${((dragN - 1.31) / 1.31 * 100).toFixed(1)}%`],
                    ['Cd', Cd.toFixed(4), '0.490', `${((Cd - 0.490) / 0.490 * 100).toFixed(1)}%`],
                    ['CdA (cm²)', CdAval.toFixed(1), '110', `${((CdAval - 110) / 110 * 100).toFixed(1)}%`],
                ],
                theme: 'plain',
                styles: {
                    fillColor: [25, 30, 35],
                    textColor: [255, 255, 255],
                    fontSize: 9,
                    cellPadding: 4
                },
                headStyles: {
                    fillColor: [100, 100, 110],
                    textColor: [255, 255, 255],
                    fontStyle: 'bold'
                },
                margin: { left: margin, right: margin }
            });

            doc.setTextColor(...colors.secondary);
            doc.setFontSize(8);
            doc.text('* Reference: AeroCloud TTTR28_22_TSV3 at 15° yaw', margin + 8, doc.lastAutoTable.finalY + 8);
        }

        // === PAGE 3: CONVERGENCE CHART ===
        doc.addPage();

        doc.setFillColor(...colors.dark);
        doc.rect(0, 0, pageWidth, pageHeight, 'F');
        doc.setFillColor(...colors.primary);
        doc.rect(0, 0, pageWidth, 3, 'F');

        doc.setTextColor(...colors.text);
        doc.setFontSize(16);
        doc.setFont('helvetica', 'bold');
        doc.text('CONVERGENCE ANALYSIS', margin, 20);

        // Capture convergence chart as image
        const chartCanvas = document.getElementById('convergence-chart');
        if (chartCanvas && convergenceChart) {
            try {
                const chartImage = chartCanvas.toDataURL('image/png', 1.0);
                doc.addImage(chartImage, 'PNG', margin, 30, pageWidth - 2*margin, 80);
            } catch (e) {
                doc.setTextColor(...colors.secondary);
                doc.setFontSize(10);
                doc.text('Chart image could not be captured', pageWidth/2, 70, { align: 'center' });
            }
        }

        // Convergence statistics
        doc.setFillColor(25, 30, 35);
        doc.roundedRect(margin, 120, pageWidth - 2*margin, 40, 3, 3, 'F');

        doc.setTextColor(...colors.primary);
        doc.setFontSize(10);
        doc.setFont('helvetica', 'bold');
        doc.text('CONVERGENCE STATISTICS', margin + 8, 132);

        doc.setFontSize(9);
        doc.setFont('helvetica', 'normal');
        const iterations = document.getElementById('iterations')?.textContent || '0';
        const residual = document.getElementById('residual-value')?.textContent || '--';

        doc.setTextColor(...colors.secondary);
        doc.text('Total Iterations:', margin + 8, 145);
        doc.text('Final Residual:', margin + 8, 155);

        doc.setTextColor(...colors.text);
        doc.text(iterations, margin + 50, 145);
        doc.text(residual, margin + 50, 155);

        doc.setTextColor(...colors.secondary);
        doc.text('Convergence Status:', margin + 100, 145);
        doc.setTextColor(...colors.success);
        doc.text(results.converged !== false ? 'CONVERGED' : 'NOT CONVERGED', margin + 145, 145);

        // Methodology section
        doc.setFillColor(25, 30, 35);
        doc.roundedRect(margin, 170, pageWidth - 2*margin, 70, 3, 3, 'F');

        doc.setTextColor(...colors.primary);
        doc.setFontSize(10);
        doc.setFont('helvetica', 'bold');
        doc.text('METHODOLOGY', margin + 8, 182);

        const methodology = [
            ['CFD Solver', 'OpenFOAM simpleFoam (SIMPLE algorithm)'],
            ['Turbulence Model', 'k-omega SST'],
            ['Reference Area', `${Aref} m² (AeroCloud standard)`],
            ['Air Density', `${rho} kg/m³`],
            ['Dynamic Pressure', `${q.toFixed(2)} Pa`],
            ['Reynolds Number', config.reynolds ? config.reynolds.toLocaleString() : 'N/A']
        ];

        doc.setFontSize(9);
        doc.setFont('helvetica', 'normal');
        methodology.forEach(([label, value], i) => {
            const y = 195 + i * 10;
            doc.setTextColor(...colors.secondary);
            doc.text(label + ':', margin + 8, y);
            doc.setTextColor(...colors.text);
            doc.text(value, margin + 55, y);
        });

        // Footer on each page
        const totalPages = doc.internal.getNumberOfPages();
        for (let i = 1; i <= totalPages; i++) {
            doc.setPage(i);
            doc.setFillColor(...colors.dark);
            doc.setTextColor(...colors.secondary);
            doc.setFontSize(8);
            doc.text(
                `WheelFlow Report | ${job.name || 'Simulation'} | Page ${i} of ${totalPages}`,
                pageWidth / 2,
                pageHeight - 8,
                { align: 'center' }
            );
        }

        // Save PDF
        const filename = `WheelFlow_${(job.name || 'simulation').replace(/[^a-zA-Z0-9]/g, '_')}_${new Date().toISOString().slice(0,10)}.pdf`;
        doc.save(filename);

        console.log('PDF exported:', filename);

    } catch (error) {
        console.error('PDF export error:', error);
        alert('Failed to generate PDF: ' + error.message);
    } finally {
        btn.classList.remove('loading');
    }
}

// Excel Export with Multiple Sheets
async function exportExcel() {
    if (!currentJobId) {
        alert('No simulation data available');
        return;
    }

    const dropdown = document.querySelector('.export-dropdown');
    dropdown.classList.remove('open');

    const btn = document.querySelector('.export-btn-main');
    btn.classList.add('loading');

    try {
        const response = await fetch(`/api/jobs/${currentJobId}`);
        const job = await response.json();

        const results = job.results || {};
        const config = job.config || {};
        const coefficients = results.coefficients || {};
        const forces = results.forces || {};

        // Calculate derived values
        const rho = 1.225;
        const U = config.speed || 13.9;
        const Aref = config.aref || results.aref || 0.0225;
        const q = 0.5 * rho * U * U;

        const Cd = coefficients.Cd || 0;
        const Cl = coefficients.Cl || 0;
        const Cm = coefficients.Cm || 0;
        const dragN = forces.drag_N || (Cd * q * Aref);
        const liftN = forces.lift_N || (Cl * q * Aref);
        const CdAval = results.CdA ? results.CdA * 10000 : (Cd * Aref * 10000);

        // Create workbook
        const wb = XLSX.utils.book_new();

        // Sheet 1: Summary
        const summaryData = [
            ['WheelFlow CFD Simulation Report'],
            [''],
            ['Simulation Information'],
            ['Name', job.name || 'Unnamed'],
            ['Job ID', currentJobId],
            ['Status', job.status || 'Unknown'],
            ['Date', new Date().toISOString()],
            [''],
            ['Key Results'],
            ['CdA (cm²)', CdAval.toFixed(1)],
            ['Drag Force (N)', dragN.toFixed(3)],
            ['Lift Force (N)', liftN.toFixed(3)],
            ['Cd', Cd.toFixed(4)],
            ['Cl', Cl.toFixed(4)],
            ['Cm', Cm.toFixed(4)],
        ];
        const wsSummary = XLSX.utils.aoa_to_sheet(summaryData);

        // Set column widths
        wsSummary['!cols'] = [{ wch: 25 }, { wch: 30 }];

        XLSX.utils.book_append_sheet(wb, wsSummary, 'Summary');

        // Sheet 2: Forces
        const forcesData = [
            ['Force Analysis'],
            [''],
            ['Parameter', 'Value', 'Unit', 'Description'],
            ['Drag Force (Fd)', dragN.toFixed(4), 'N', 'Force in flow direction'],
            ['Lift Force (Fl)', liftN.toFixed(4), 'N', 'Force perpendicular to flow'],
            ['Side Force (Fs)', (forces.side_N || 0).toFixed(4), 'N', 'Lateral force'],
            [''],
            ['Moment Analysis'],
            ['Roll Moment', (coefficients.Mx || 0).toFixed(4), 'N·m', 'About X-axis'],
            ['Pitch Moment', (coefficients.My || 0).toFixed(4), 'N·m', 'About Y-axis'],
            ['Yaw Moment', (coefficients.Mz || 0).toFixed(4), 'N·m', 'About Z-axis'],
        ];
        const wsForces = XLSX.utils.aoa_to_sheet(forcesData);
        wsForces['!cols'] = [{ wch: 20 }, { wch: 15 }, { wch: 10 }, { wch: 30 }];
        XLSX.utils.book_append_sheet(wb, wsForces, 'Forces');

        // Sheet 3: Coefficients
        const coeffData = [
            ['Aerodynamic Coefficients'],
            [''],
            ['Coefficient', 'Value', 'Definition'],
            ['Cd (Drag)', Cd.toFixed(6), 'Fd / (q × Aref)'],
            ['Cl (Lift)', Cl.toFixed(6), 'Fl / (q × Aref)'],
            ['Cs (Side)', (coefficients.Cs || 0).toFixed(6), 'Fs / (q × Aref)'],
            ['Cm (Moment)', Cm.toFixed(6), 'M / (q × Aref × L)'],
            [''],
            ['Coefficient × Area'],
            ['CdA', (Cd * Aref * 10000).toFixed(2), 'cm²'],
            ['ClA', (Cl * Aref * 10000).toFixed(2), 'cm²'],
            ['CsA', ((coefficients.Cs || 0) * Aref * 10000).toFixed(2), 'cm²'],
            [''],
            ['Reference Values'],
            ['Reference Area (Aref)', Aref, 'm²'],
            ['Dynamic Pressure (q)', q.toFixed(2), 'Pa'],
        ];
        const wsCoeff = XLSX.utils.aoa_to_sheet(coeffData);
        wsCoeff['!cols'] = [{ wch: 25 }, { wch: 15 }, { wch: 20 }];
        XLSX.utils.book_append_sheet(wb, wsCoeff, 'Coefficients');

        // Sheet 4: Input Parameters
        const inputData = [
            ['Simulation Input Parameters'],
            [''],
            ['Flow Conditions'],
            ['Flow Speed', config.speed || 13.9, 'm/s'],
            ['Speed (km/h)', Math.round((config.speed || 13.9) * 3.6), 'km/h'],
            ['Yaw Angle', config.yaw_angles?.[0] || 0, '°'],
            ['Air Density (ρ)', rho, 'kg/m³'],
            ['Kinematic Viscosity (ν)', 1.48e-5, 'm²/s'],
            ['Reynolds Number', config.reynolds || 'N/A', '-'],
            [''],
            ['Geometry Settings'],
            ['Wheel Radius', config.wheel_radius || 0.325, 'm'],
            ['Ground Simulation', config.ground_enabled !== false ? 'Enabled' : 'Disabled', ''],
            ['Ground Type', config.ground_type || 'moving', ''],
            ['Wheel Rotation', config.rolling_enabled ? 'Enabled' : 'Disabled', ''],
            ['Rotation Method', config.rotation_method || 'none', ''],
            ['Angular Velocity (ω)', config.omega || 'N/A', 'rad/s'],
            [''],
            ['Mesh Settings'],
            ['Quality Level', config.quality || 'standard', ''],
            ['Estimated Cells', config.quality === 'pro' ? '~8M' : config.quality === 'basic' ? '~500K' : '~2M', ''],
        ];
        const wsInput = XLSX.utils.aoa_to_sheet(inputData);
        wsInput['!cols'] = [{ wch: 25 }, { wch: 15 }, { wch: 10 }];
        XLSX.utils.book_append_sheet(wb, wsInput, 'Input Parameters');

        // Try to get convergence data for additional sheet
        try {
            const convResponse = await fetch(`/api/jobs/${currentJobId}/convergence`);
            if (convResponse.ok) {
                const convData = await convResponse.json();
                if (convData.time && convData.time.length > 0) {
                    const convergenceRows = [
                        ['Convergence History'],
                        [''],
                        ['Iteration', 'Cd', 'Cl', 'Cm']
                    ];

                    // Sample every N points to keep file size reasonable
                    const step = Math.max(1, Math.floor(convData.time.length / 500));
                    for (let i = 0; i < convData.time.length; i += step) {
                        convergenceRows.push([
                            convData.time[i],
                            convData.Cd?.[i]?.toFixed(6) || '',
                            convData.Cl?.[i]?.toFixed(6) || '',
                            convData.Cm?.[i]?.toFixed(6) || ''
                        ]);
                    }

                    const wsConv = XLSX.utils.aoa_to_sheet(convergenceRows);
                    wsConv['!cols'] = [{ wch: 12 }, { wch: 12 }, { wch: 12 }, { wch: 12 }];
                    XLSX.utils.book_append_sheet(wb, wsConv, 'Convergence');
                }
            }
        } catch (e) {
            console.log('Could not fetch convergence data for Excel:', e);
        }

        // Generate filename and save
        const filename = `WheelFlow_${(job.name || 'simulation').replace(/[^a-zA-Z0-9]/g, '_')}_${new Date().toISOString().slice(0,10)}.xlsx`;
        XLSX.writeFile(wb, filename);

        console.log('Excel exported:', filename);

    } catch (error) {
        console.error('Excel export error:', error);
        alert('Failed to generate Excel file: ' + error.message);
    } finally {
        btn.classList.remove('loading');
    }
}

// CSV Export (enhanced)
function exportCSV() {
    if (!currentJobId) {
        alert('No simulation data available');
        return;
    }

    const dropdown = document.querySelector('.export-dropdown');
    if (dropdown) dropdown.classList.remove('open');

    fetch(`/api/jobs/${currentJobId}`)
        .then(res => res.json())
        .then(job => {
            const results = job.results || {};
            const coefficients = results.coefficients || {};
            const config = job.config || {};

            // Calculate derived values
            const rho = 1.225;
            const U = config.speed || 13.9;
            const Aref = config.aref || results.aref || 0.0225;
            const q = 0.5 * rho * U * U;

            const Cd = coefficients.Cd || 0;
            const Cl = coefficients.Cl || 0;
            const Cm = coefficients.Cm || 0;
            const dragN = results.forces?.drag_N || (Cd * q * Aref);
            const liftN = results.forces?.lift_N || (Cl * q * Aref);
            const CdA = results.CdA ? (results.CdA * 10000).toFixed(2) : (Cd * Aref * 10000).toFixed(2);

            const csvContent = [
                '# WheelFlow CFD Results',
                '# Generated: ' + new Date().toISOString(),
                '',
                'Section,Parameter,Value,Unit',
                'Info,Job ID,' + currentJobId + ',',
                'Info,Name,' + (job.name || '') + ',',
                'Info,Status,' + (job.status || '') + ',',
                '',
                'Config,Speed,' + (config.speed || 13.9) + ',m/s',
                'Config,Speed,' + Math.round((config.speed || 13.9) * 3.6) + ',km/h',
                'Config,Yaw Angle,' + (config.yaw_angles?.[0] || 0) + ',deg',
                'Config,Quality,' + (config.quality || 'standard') + ',',
                'Config,Ground,' + (config.ground_enabled !== false ? 'enabled' : 'disabled') + ',',
                'Config,Wheel Radius,' + (config.wheel_radius || 0.325) + ',m',
                '',
                'Results,Drag Force,' + dragN.toFixed(4) + ',N',
                'Results,Lift Force,' + liftN.toFixed(4) + ',N',
                'Results,Cd,' + Cd.toFixed(6) + ',',
                'Results,Cl,' + Cl.toFixed(6) + ',',
                'Results,Cm,' + Cm.toFixed(6) + ',',
                'Results,CdA,' + CdA + ',cm²',
                '',
                'Reference,Aref,' + Aref + ',m²',
                'Reference,Dynamic Pressure,' + q.toFixed(2) + ',Pa',
                'Reference,Air Density,' + rho + ',kg/m³'
            ].join('\n');

            const blob = new Blob([csvContent], { type: 'text/csv' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `WheelFlow_${(job.name || 'simulation').replace(/[^a-zA-Z0-9]/g, '_')}_${new Date().toISOString().slice(0,10)}.csv`;
            a.click();
            URL.revokeObjectURL(url);

            console.log('CSV exported');
        })
        .catch(error => {
            console.error('CSV export error:', error);
            alert('Failed to export CSV: ' + error.message);
        });
}

// Chart Image Export
function exportChartImage() {
    const dropdown = document.querySelector('.export-dropdown');
    if (dropdown) dropdown.classList.remove('open');

    const chartCanvas = document.getElementById('convergence-chart');
    if (!chartCanvas) {
        alert('No chart available to export');
        return;
    }

    try {
        // Create a temporary canvas with white background
        const tempCanvas = document.createElement('canvas');
        const ctx = tempCanvas.getContext('2d');

        // Make it higher resolution
        const scale = 2;
        tempCanvas.width = chartCanvas.width * scale;
        tempCanvas.height = chartCanvas.height * scale;

        // Fill with dark background (matching dashboard theme)
        ctx.fillStyle = '#0f1419';
        ctx.fillRect(0, 0, tempCanvas.width, tempCanvas.height);

        // Draw chart
        ctx.scale(scale, scale);
        ctx.drawImage(chartCanvas, 0, 0);

        // Add title
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 14px Arial';
        ctx.fillText('WheelFlow - Convergence Chart', 10, 20);

        // Add timestamp
        ctx.fillStyle = '#8b98a5';
        ctx.font = '10px Arial';
        ctx.fillText(new Date().toLocaleString(), 10, chartCanvas.height - 10);

        // Convert to PNG and download
        const dataUrl = tempCanvas.toDataURL('image/png', 1.0);
        const a = document.createElement('a');
        a.href = dataUrl;
        a.download = `WheelFlow_convergence_chart_${new Date().toISOString().slice(0,10)}.png`;
        a.click();

        console.log('Chart image exported');

    } catch (error) {
        console.error('Chart export error:', error);
        alert('Failed to export chart image: ' + error.message);
    }
}

// Chart button handlers
document.querySelectorAll('.chart-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        const series = btn.dataset.series;
        if (convergenceChart) {
            convergenceChart.data.datasets[0].label = series === 'cd' ? 'Cd' : 'Residual';
            convergenceChart.options.scales.y.title.text = series === 'cd' ? 'Cd' : 'log(residual)';
            convergenceChart.update();
        }
    });
});

// Yaw button handlers
document.querySelectorAll('.yaw-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.yaw-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        // TODO: Load results for selected yaw angle
    });
});

// Initialize 3D Viewer for pressure visualization
function init3DViewer() {
    const container = document.getElementById('pressure-viewer');
    if (!container || viewer3dInitialized) return;

    // Check if Three.js is available
    if (typeof THREE === 'undefined') {
        showViewerMessage('Three.js not loaded', 'error');
        return;
    }

    try {
        const width = container.clientWidth || 400;
        const height = container.clientHeight || 300;

        // Scene
        scene3d = new THREE.Scene();
        scene3d.background = new THREE.Color(0x0f1419);

        // Camera
        camera3d = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
        camera3d.position.set(1.5, 1, 1.5);

        // Renderer
        renderer3d = new THREE.WebGLRenderer({ antialias: true });
        renderer3d.setSize(width, height);
        renderer3d.setPixelRatio(Math.min(window.devicePixelRatio, 2));

        // Controls
        if (typeof THREE.OrbitControls !== 'undefined') {
            controls3d = new THREE.OrbitControls(camera3d, renderer3d.domElement);
            controls3d.enableDamping = true;
            controls3d.dampingFactor = 0.05;
            controls3d.minDistance = 0.5;
            controls3d.maxDistance = 5;
        }

        // Lights
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        scene3d.add(ambientLight);

        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(5, 5, 5);
        scene3d.add(directionalLight);

        // Add placeholder wheel geometry
        createPlaceholderWheel();

        // Hide placeholder text
        const placeholder = container.querySelector('.viewer-placeholder');
        if (placeholder) placeholder.style.display = 'none';

        // Append canvas
        container.appendChild(renderer3d.domElement);

        // Animation loop
        function animate() {
            requestAnimationFrame(animate);
            if (controls3d) controls3d.update();
            renderer3d.render(scene3d, camera3d);
        }
        animate();

        // Handle resize
        const resizeObserver = new ResizeObserver(() => {
            const w = container.clientWidth;
            const h = container.clientHeight;
            camera3d.aspect = w / h;
            camera3d.updateProjectionMatrix();
            renderer3d.setSize(w, h);
        });
        resizeObserver.observe(container);

        viewer3dInitialized = true;
        console.log('3D viewer initialized');

    } catch (error) {
        console.error('3D viewer init error:', error);
        showViewerMessage('3D viewer error: ' + error.message, 'error');
    }
}

// Create a placeholder wheel geometry
function createPlaceholderWheel() {
    if (!scene3d) return;

    // Remove existing wheel
    if (wheelMesh) {
        scene3d.remove(wheelMesh);
    }

    // Create a simple torus to represent a wheel
    const geometry = new THREE.TorusGeometry(0.35, 0.03, 16, 50);
    const material = new THREE.MeshPhongMaterial({
        color: 0x1d9bf0,
        specular: 0x444444,
        shininess: 30,
    });

    wheelMesh = new THREE.Mesh(geometry, material);
    wheelMesh.rotation.x = Math.PI / 2;
    scene3d.add(wheelMesh);

    // Add hub
    const hubGeometry = new THREE.CylinderGeometry(0.04, 0.04, 0.04, 16);
    const hubMaterial = new THREE.MeshPhongMaterial({ color: 0x333333 });
    const hub = new THREE.Mesh(hubGeometry, hubMaterial);
    hub.rotation.x = Math.PI / 2;
    wheelMesh.add(hub);

    // Add spokes
    for (let i = 0; i < 16; i++) {
        const angle = (i / 16) * Math.PI * 2;
        const spokeGeometry = new THREE.CylinderGeometry(0.002, 0.002, 0.3, 4);
        const spoke = new THREE.Mesh(spokeGeometry, hubMaterial);
        spoke.position.set(Math.cos(angle) * 0.15, Math.sin(angle) * 0.15, 0);
        spoke.rotation.z = angle + Math.PI / 2;
        wheelMesh.add(spoke);
    }

    camera3d.lookAt(0, 0, 0);
}

// Show message in 3D viewer area
function showViewerMessage(message, type = 'info') {
    const container = document.getElementById('pressure-viewer');
    if (!container) return;

    let placeholder = container.querySelector('.viewer-placeholder');
    if (!placeholder) {
        placeholder = document.createElement('div');
        placeholder.className = 'viewer-placeholder';
        container.appendChild(placeholder);
    }

    placeholder.style.display = 'flex';
    placeholder.innerHTML = `<span style="color: ${type === 'error' ? '#e10600' : '#8b98a5'}">${message}</span>`;
}

// Initialize view buttons with tooltips
function initViewButtons() {
    const viewButtons = document.querySelectorAll('.view-btn');
    const tooltips = {
        'front': 'Front View (Y-Z plane)',
        'side': 'Side View (X-Z plane)',
        'top': 'Top View (X-Y plane)',
        'iso': 'Isometric 3D View'
    };

    viewButtons.forEach(btn => {
        const view = btn.dataset.view;
        if (tooltips[view]) {
            btn.title = tooltips[view];
        }

        btn.addEventListener('click', () => {
            viewButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            setViewAngle(view);
        });
    });
}

// Set camera to specific view angle
function setViewAngle(view) {
    if (!camera3d) return;

    const distance = 2;
    switch (view) {
        case 'front':
            camera3d.position.set(0, 0, distance);
            break;
        case 'side':
            camera3d.position.set(distance, 0, 0);
            break;
        case 'top':
            camera3d.position.set(0, distance, 0);
            break;
        case 'iso':
        default:
            camera3d.position.set(1.5, 1, 1.5);
            break;
    }
    camera3d.lookAt(0, 0, 0);
    if (controls3d) controls3d.update();
}

// Initialize speedometer
function initSpeedometer() {
    const speedDialFill = document.getElementById('speed-dial-fill');
    if (!speedDialFill) return;

    // Set initial arc length for SVG path
    const pathLength = speedDialFill.getTotalLength ? speedDialFill.getTotalLength() : 157;
    speedDialFill.style.strokeDasharray = pathLength;
    speedDialFill.style.strokeDashoffset = pathLength;
}

// Update speedometer based on speed value
function updateSpeedometer(speedKmh, maxSpeed = 80) {
    const speedDialFill = document.getElementById('speed-dial-fill');
    if (!speedDialFill) return;

    const pathLength = speedDialFill.getTotalLength ? speedDialFill.getTotalLength() : 157;
    const percent = Math.min(speedKmh / maxSpeed, 1);
    const offset = pathLength * (1 - percent);

    speedDialFill.style.strokeDashoffset = offset;
}

// Load actual pressure surface from simulation
async function loadPressureSurface(jobId) {
    if (!scene3d || !jobId) return;

    try {
        // Fetch JSON geometry with pressure data
        const response = await fetch(`/api/jobs/${jobId}/viz/pressure_surface.json`);
        if (!response.ok) {
            console.log('Pressure surface not available yet');
            return;
        }

        const data = await response.json();

        if (!data.vertices || !data.indices || data.vertices.length === 0) {
            console.log('Pressure surface data incomplete');
            return;
        }

        // Remove existing wheel mesh
        if (wheelMesh) {
            scene3d.remove(wheelMesh);
            wheelMesh = null;
        }

        // Create BufferGeometry from JSON data
        const geometry = new THREE.BufferGeometry();

        // Set vertices
        const vertices = new Float32Array(data.vertices);
        geometry.setAttribute('position', new THREE.BufferAttribute(vertices, 3));

        // Set indices
        const indices = new Uint32Array(data.indices);
        geometry.setIndex(new THREE.BufferAttribute(indices, 1));

        // Compute normals for proper lighting
        geometry.computeVertexNormals();

        // Create vertex colors based on pressure
        const colors = createPressureColors(
            data.vertices,
            data.indices,
            data.pressures,
            data.pressure_range
        );
        geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

        // Create mesh with vertex colors
        const material = new THREE.MeshPhongMaterial({
            vertexColors: true,
            side: THREE.DoubleSide,
            shininess: 30,
            specular: 0x222222
        });

        wheelMesh = new THREE.Mesh(geometry, material);

        // Center the geometry
        geometry.computeBoundingBox();
        const center = new THREE.Vector3();
        geometry.boundingBox.getCenter(center);
        wheelMesh.position.sub(center);

        scene3d.add(wheelMesh);

        // Update camera to fit the new geometry
        const box = geometry.boundingBox;
        const size = box.getSize(new THREE.Vector3());
        const maxDim = Math.max(size.x, size.y, size.z);
        camera3d.position.set(maxDim * 2, maxDim * 1.5, maxDim * 2);
        camera3d.lookAt(0, 0, 0);
        if (controls3d) {
            controls3d.target.set(0, 0, 0);
            controls3d.update();
        }

        // Update pressure range display
        if (data.pressure_range) {
            const pMin = data.pressure_range[0].toFixed(1);
            const pMax = data.pressure_range[1].toFixed(1);
            const legendEl = document.getElementById('pressure-legend');
            if (legendEl) {
                legendEl.textContent = `Pressure: ${pMin} to ${pMax} Pa`;
            }
        }

        console.log(`Pressure surface loaded: ${data.n_vertices} vertices, ${data.n_triangles} triangles`);

    } catch (error) {
        console.log('Could not load pressure surface:', error);
    }
}

// Create vertex colors based on face pressure values
function createPressureColors(vertices, indices, pressures, pressureRange) {
    const numVertices = vertices.length / 3;
    const colors = new Float32Array(numVertices * 3);

    // Default to gray if no pressure data
    if (!pressures || pressures.length === 0) {
        for (let i = 0; i < numVertices; i++) {
            colors[i * 3] = 0.7;     // R
            colors[i * 3 + 1] = 0.7; // G
            colors[i * 3 + 2] = 0.7; // B
        }
        return colors;
    }

    // Determine pressure range
    let pMin, pMax;
    if (pressureRange && pressureRange.length === 2) {
        pMin = pressureRange[0];
        pMax = pressureRange[1];
    } else {
        pMin = Math.min(...pressures);
        pMax = Math.max(...pressures);
    }

    // Ensure range is not zero
    if (pMax - pMin < 1e-10) {
        pMax = pMin + 1;
    }

    // Accumulate colors per vertex from adjacent faces
    const vertexPressureSum = new Float32Array(numVertices);
    const vertexPressureCount = new Uint32Array(numVertices);

    // Each face has 3 indices (triangulated)
    const numTriangles = indices.length / 3;
    for (let tri = 0; tri < numTriangles; tri++) {
        // Map triangle back to original face for pressure lookup
        const faceIndex = Math.min(tri, pressures.length - 1);
        const p = pressures[faceIndex];

        const i0 = indices[tri * 3];
        const i1 = indices[tri * 3 + 1];
        const i2 = indices[tri * 3 + 2];

        vertexPressureSum[i0] += p;
        vertexPressureSum[i1] += p;
        vertexPressureSum[i2] += p;

        vertexPressureCount[i0]++;
        vertexPressureCount[i1]++;
        vertexPressureCount[i2]++;
    }

    // Convert averaged pressure to color (blue-white-red diverging colormap)
    for (let i = 0; i < numVertices; i++) {
        let p;
        if (vertexPressureCount[i] > 0) {
            p = vertexPressureSum[i] / vertexPressureCount[i];
        } else {
            p = (pMin + pMax) / 2;
        }

        // Normalize to [0, 1]
        const t = Math.max(0, Math.min(1, (p - pMin) / (pMax - pMin)));

        // Blue-white-red diverging colormap
        let r, g, b;
        if (t < 0.5) {
            // Blue to white (low pressure)
            const s = t * 2;
            r = s;
            g = s;
            b = 1.0;
        } else {
            // White to red (high pressure)
            const s = (t - 0.5) * 2;
            r = 1.0;
            g = 1.0 - s;
            b = 1.0 - s;
        }

        colors[i * 3] = r;
        colors[i * 3 + 1] = g;
        colors[i * 3 + 2] = b;
    }

    return colors;
}

// Pressure Slice Viewer Functions
async function loadAvailableSlices() {
    if (!currentJobId) return;

    try {
        const response = await fetch(`/api/jobs/${currentJobId}/viz/slices`);
        if (!response.ok) return;

        const data = await response.json();
        const selector = document.getElementById('slice-selector');
        if (!selector) return;

        // Clear existing options except the first
        while (selector.options.length > 1) {
            selector.remove(1);
        }

        // Add available slices
        if (data.slices && data.slices.length > 0) {
            const sliceNames = {
                'y-slice-0': 'Y=0 (Center)',
                'y-slice-neg02': 'Y=-0.02',
                'y-slice-pos02': 'Y=+0.02',
                'x-slice-0': 'X=0',
                'z-slice': 'Z slice'
            };

            for (const slice of data.slices) {
                const opt = document.createElement('option');
                opt.value = slice.name.replace('.vtk', '');
                opt.textContent = sliceNames[slice.type] || slice.name;
                selector.appendChild(opt);
            }
        }
    } catch (error) {
        console.log('Could not load available slices:', error);
    }
}

async function loadSliceImage() {
    const selector = document.getElementById('slice-selector');
    if (!selector || !selector.value || !currentJobId) return;

    const sliceName = selector.value;
    const container = document.getElementById('slice-container');
    const placeholder = document.getElementById('slice-placeholder');
    const loading = document.getElementById('slice-loading');
    const image = document.getElementById('slice-image');

    if (!container || !image) return;

    // Show loading state
    if (placeholder) placeholder.classList.add('hidden');
    if (loading) loading.classList.remove('hidden');
    image.classList.add('hidden');

    try {
        const imageUrl = `/api/jobs/${currentJobId}/viz/slice/${sliceName}.png`;

        // Create a new image to test loading
        const testImg = new Image();
        testImg.onload = () => {
            image.src = imageUrl;
            image.classList.remove('hidden');
            if (loading) loading.classList.add('hidden');
        };
        testImg.onerror = () => {
            console.log('Slice image not available');
            if (loading) loading.classList.add('hidden');
            if (placeholder) {
                placeholder.classList.remove('hidden');
                placeholder.querySelector('span').textContent = 'Slice image unavailable';
            }
        };
        testImg.src = imageUrl;

    } catch (error) {
        console.log('Error loading slice image:', error);
        if (loading) loading.classList.add('hidden');
        if (placeholder) placeholder.classList.remove('hidden');
    }
}

function downloadSliceImage() {
    const image = document.getElementById('slice-image');
    if (!image || image.classList.contains('hidden') || !image.src) {
        alert('No slice image to download');
        return;
    }

    const link = document.createElement('a');
    link.href = image.src;
    link.download = `pressure_slice_${currentJobId}.png`;
    link.click();
}

// Parts Breakdown Chart
let partsBreakdownChart = null;

/**
 * Initialize the parts breakdown doughnut chart
 */
function initPartsBreakdownChart() {
    const ctx = document.getElementById('parts-breakdown-chart');
    if (!ctx) return;

    partsBreakdownChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: [],
            datasets: [{
                data: [],
                backgroundColor: [
                    '#e10600',  // Red - rim
                    '#0090ff',  // Blue - tire
                    '#00d26a',  // Green - spokes
                    '#ffd700',  // Yellow - hub
                    '#9d4edd'   // Purple - disc
                ],
                borderColor: '#0a0a0f',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '60%',
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed || 0;
                            const dataset = context.dataset;
                            const total = dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                            return `${label}: ${percentage}% drag`;
                        }
                    }
                }
            }
        }
    });
}

/**
 * Load and display parts breakdown data
 */
async function loadPartsBreakdown(jobId) {
    if (!jobId) return;

    const container = document.getElementById('breakdown-container');
    const placeholder = document.getElementById('breakdown-placeholder');
    const legend = document.getElementById('breakdown-legend');

    if (!container) return;

    try {
        const response = await fetch(`/api/jobs/${jobId}/parts_breakdown`);

        if (!response.ok) {
            console.log('Parts breakdown not available');
            return;
        }

        const data = await response.json();

        if (!data.has_parts || !data.parts || data.parts.length === 0) {
            // Show placeholder
            if (placeholder) placeholder.classList.remove('hidden');
            if (partsBreakdownChart) {
                partsBreakdownChart.data.labels = [];
                partsBreakdownChart.data.datasets[0].data = [];
                partsBreakdownChart.update();
            }
            return;
        }

        // Hide placeholder
        if (placeholder) placeholder.classList.add('hidden');

        // Initialize chart if needed
        if (!partsBreakdownChart) {
            initPartsBreakdownChart();
        }

        // Update chart data
        const labels = data.parts.map(p => capitalizeFirst(p.name));
        const values = data.parts.map(p => Math.abs(p.Cd));

        partsBreakdownChart.data.labels = labels;
        partsBreakdownChart.data.datasets[0].data = values;
        partsBreakdownChart.update();

        // Update legend
        if (legend) {
            const colors = partsBreakdownChart.data.datasets[0].backgroundColor;
            const total = values.reduce((a, b) => a + b, 0);

            legend.innerHTML = data.parts.map((part, i) => {
                const percent = total > 0 ? ((Math.abs(part.Cd) / total) * 100).toFixed(1) : 0;
                return `
                    <div class="breakdown-legend-item">
                        <span class="breakdown-legend-color" style="background: ${colors[i % colors.length]}"></span>
                        <span>${capitalizeFirst(part.name)}</span>
                        <span class="breakdown-legend-value">${percent}%</span>
                    </div>
                `;
            }).join('');
        }

        console.log('Parts breakdown loaded:', data.parts.length, 'parts');

    } catch (error) {
        console.log('Could not load parts breakdown:', error);
    }
}

/**
 * Capitalize first letter of a string
 */
function capitalizeFirst(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}

// Hero Image Functions
let heroImageJobId = null;

/**
 * Show hero loading state
 */
function showHeroLoading() {
    const loading = document.getElementById('hero-loading');
    const image = document.getElementById('hero-image');
    const error = document.getElementById('hero-error');
    const placeholder = document.getElementById('hero-placeholder');

    if (loading) loading.classList.remove('hidden');
    if (image) image.classList.add('hidden');
    if (error) error.classList.add('hidden');
    if (placeholder) placeholder.classList.add('hidden');
}

/**
 * Show hero image
 */
function showHeroImage() {
    const loading = document.getElementById('hero-loading');
    const image = document.getElementById('hero-image');
    const error = document.getElementById('hero-error');
    const placeholder = document.getElementById('hero-placeholder');

    if (loading) loading.classList.add('hidden');
    if (image) image.classList.remove('hidden');
    if (error) error.classList.add('hidden');
    if (placeholder) placeholder.classList.add('hidden');
}

/**
 * Show hero error state
 */
function showHeroError(message) {
    const loading = document.getElementById('hero-loading');
    const image = document.getElementById('hero-image');
    const error = document.getElementById('hero-error');
    const placeholder = document.getElementById('hero-placeholder');
    const errorMsg = document.getElementById('hero-error-msg');

    if (loading) loading.classList.add('hidden');
    if (image) image.classList.add('hidden');
    if (error) error.classList.remove('hidden');
    if (placeholder) placeholder.classList.add('hidden');
    if (errorMsg) errorMsg.textContent = message || 'Generation failed';
}

/**
 * Show hero placeholder state
 */
function showHeroPlaceholder() {
    const loading = document.getElementById('hero-loading');
    const image = document.getElementById('hero-image');
    const error = document.getElementById('hero-error');
    const placeholder = document.getElementById('hero-placeholder');

    if (loading) loading.classList.add('hidden');
    if (image) image.classList.add('hidden');
    if (error) error.classList.add('hidden');
    if (placeholder) placeholder.classList.remove('hidden');
}

/**
 * Load and display the hero image
 */
async function loadHeroImage(jobId, regenerate = false) {
    if (!jobId) return;

    heroImageJobId = jobId;
    showHeroLoading();

    try {
        const url = regenerate
            ? `/api/jobs/${jobId}/viz/hero.png?regenerate=true`
            : `/api/jobs/${jobId}/viz/hero.png`;

        const response = await fetch(url);

        if (response.ok) {
            const blob = await response.blob();
            const imageUrl = URL.createObjectURL(blob);
            const heroImage = document.getElementById('hero-image');

            if (heroImage) {
                heroImage.src = imageUrl;
                heroImage.onload = () => {
                    showHeroImage();
                    console.log('Hero image loaded successfully');
                };
                heroImage.onerror = () => {
                    showHeroError('Image load failed');
                };
            }
        } else if (response.status === 503) {
            showHeroError('ParaView unavailable');
        } else if (response.status === 504) {
            showHeroError('Generation timeout');
        } else if (response.status === 404) {
            showHeroPlaceholder();
        } else {
            showHeroError(`Error ${response.status}`);
        }
    } catch (error) {
        console.log('Could not load hero image:', error);
        showHeroError('Network error');
    }
}

/**
 * Regenerate the hero image
 */
function regenerateHeroImage() {
    if (heroImageJobId) {
        loadHeroImage(heroImageJobId, true);
    }
}

/**
 * Download the hero image
 */
function downloadHeroImage() {
    const heroImage = document.getElementById('hero-image');
    if (heroImage && heroImage.src && !heroImage.classList.contains('hidden')) {
        const link = document.createElement('a');
        link.href = heroImage.src;
        link.download = `wheelflow_${heroImageJobId || 'hero'}_flow.png`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
}
