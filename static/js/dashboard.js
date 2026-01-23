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

                // Use real data
                convergenceChart.data.labels = data.time;
                convergenceChart.data.datasets[0].data = data.Cd;
                convergenceChart.update('none');

                // Update iteration count
                document.getElementById('iterations').textContent = data.time.length;
                document.getElementById('of-iteration').textContent = data.time.length;

                // Update residual from last value
                if (data.residual && data.residual.length > 0) {
                    const lastRes = data.residual[data.residual.length - 1];
                    document.getElementById('residual-value').textContent = lastRes.toExponential(1);
                }

                return;
            }
        }
    } catch (error) {
        console.log('Using fallback convergence data:', error);
    }

    // Fallback to simulated data if API fails
    const iterations = Math.round(job.results?.coefficients?.time || job.progress * 5);
    const finalCd = job.results?.coefficients?.Cd || 0.15;

    if (iterations > 0) {
        // Hide placeholder since we have some data
        hideChartPlaceholder('convergence-chart');

        const labels = [];
        const data = [];

        for (let i = 1; i <= iterations; i += Math.max(1, Math.floor(iterations / 50))) {
            labels.push(i);
            const progress = i / iterations;
            const noise = (1 - progress) * 0.1 * (Math.random() - 0.5);
            const value = finalCd * (1 + (1 - progress) * 2) + noise;
            data.push(value);
        }

        labels.push(iterations);
        data.push(finalCd);

        convergenceChart.data.labels = labels;
        convergenceChart.data.datasets[0].data = data;
        convergenceChart.update('none');

        // Update iteration display
        document.getElementById('iterations').textContent = iterations;
        document.getElementById('of-iteration').textContent = iterations;
    } else {
        // Show placeholder when no data
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

// Format numbers with K, M suffixes
function formatNumber(num, decimals = 1) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(decimals) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(decimals) + 'K';
    }
    return num.toFixed(decimals);
}

// Export functions
function exportPDF() {
    alert('PDF export coming soon!');
    // TODO: Implement PDF generation
}

function exportCSV() {
    if (!currentJobId) return;

    fetch(`/api/jobs/${currentJobId}`)
        .then(res => res.json())
        .then(job => {
            const results = job.results || {};
            const coefficients = results.coefficients || {};

            const csvContent = [
                'WheelFlow CFD Results',
                `Job ID,${currentJobId}`,
                `Name,${job.name}`,
                `Speed,${job.config?.speed} m/s`,
                `Yaw Angle,${job.config?.yaw_angles?.[0]}°`,
                `Quality,${job.config?.quality}`,
                '',
                'Coefficients',
                `Cd,${coefficients.Cd || ''}`,
                `Cl,${coefficients.Cl || ''}`,
                `Cm,${coefficients.Cm || ''}`,
                '',
                'Forces (Aref=0.0225 m²)',
                `Drag,${results.forces?.drag_N || ''} N`,
                `Lift,${results.forces?.lift_N || ''} N`,
                `CdA,${results.CdA ? (results.CdA * 10000).toFixed(1) : ''} cm²`
            ].join('\n');

            const blob = new Blob([csvContent], { type: 'text/csv' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `wheelflow_${currentJobId}.csv`;
            a.click();
            URL.revokeObjectURL(url);
        });
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
        // Try to load PLY file
        const response = await fetch(`/api/jobs/${jobId}/viz/pressure_surface.ply`);
        if (!response.ok) {
            console.log('Pressure surface not available yet');
            return;
        }

        // For now, just update the placeholder wheel color to indicate data loaded
        if (wheelMesh) {
            wheelMesh.material.color.setHex(0x00d26a);
        }

    } catch (error) {
        console.log('Could not load pressure surface:', error);
    }
}
