/**
 * WheelFlow - Bicycle Wheel CFD Analysis
 * Frontend Application
 */

// State
let uploadedFile = null;
let uploadedFileId = null;
let scene, camera, renderer, controls, mesh;
let wireframeMode = false;

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initUpload();
    initForm();
    initViewer();
    pollJobs();
});

// Navigation
function initNavigation() {
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const view = btn.dataset.view;
            showView(view);
            document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        });
    });
}

function showView(viewName) {
    // Remove active class from all views
    document.querySelectorAll('.view').forEach(v => {
        v.classList.remove('active');
    });

    // Add active class to the target view
    const targetView = document.getElementById(`${viewName}-view`);
    if (targetView) {
        targetView.classList.add('active');
    }

    if (viewName === 'jobs') {
        refreshJobs();
    }
}

// File Upload
function initUpload() {
    const uploadZone = document.getElementById('upload-zone');
    const fileInput = document.getElementById('file-input');

    uploadZone.addEventListener('click', () => fileInput.click());

    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });

    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('dragover');
    });

    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFile(files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });
}

// Maximum file size: 100MB
const MAX_FILE_SIZE = 100 * 1024 * 1024;

async function handleFile(file) {
    const validExtensions = ['.stl', '.obj'];
    const ext = file.name.toLowerCase().slice(file.name.lastIndexOf('.'));

    // Validate file extension
    if (!validExtensions.includes(ext)) {
        showToast('Invalid file type. Please upload an STL or OBJ file.', 'error');
        return;
    }

    // Validate file size
    if (file.size > MAX_FILE_SIZE) {
        showToast(`File too large. Maximum size is ${formatFileSize(MAX_FILE_SIZE)}.`, 'error');
        return;
    }

    // Validate file is not empty
    if (file.size === 0) {
        showToast('File is empty. Please upload a valid geometry file.', 'error');
        return;
    }

    uploadedFile = file;

    // Show file info with loading state
    const fileInfo = document.getElementById('file-info');
    fileInfo.classList.remove('hidden');
    fileInfo.querySelector('.file-name').textContent = file.name;
    fileInfo.querySelector('.file-size').textContent = formatFileSize(file.size);

    // Show upload in progress
    const uploadZone = document.getElementById('upload-zone');
    uploadZone.classList.add('uploading');

    // Upload to server
    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        // Handle specific HTTP error codes
        if (!response.ok) {
            let errorMessage = 'Upload failed';
            try {
                const errorData = await response.json();
                errorMessage = errorData.detail || errorData.message || errorMessage;
            } catch {
                // Response wasn't JSON, use status text
                if (response.status === 413) {
                    errorMessage = 'File too large for server';
                } else if (response.status === 415) {
                    errorMessage = 'Unsupported file format';
                } else if (response.status === 422) {
                    errorMessage = 'Invalid or corrupted geometry file';
                } else if (response.status >= 500) {
                    errorMessage = 'Server error. Please try again later.';
                }
            }
            throw new Error(errorMessage);
        }

        const data = await response.json();
        uploadedFileId = data.id;

        // Check for warnings from server
        if (data.warnings && data.warnings.length > 0) {
            data.warnings.forEach(warning => {
                showToast(warning, 'warning');
            });
        }

        // Update geometry info
        if (data.info) {
            updateGeometryInfo(data.info);
        }

        // Load into 3D viewer
        loadSTLInViewer(file);

        // Enable run button
        document.getElementById('run-btn').disabled = false;

        // Auto-fill name from filename
        const nameInput = document.getElementById('sim-name');
        if (!nameInput.value) {
            nameInput.value = file.name.replace(/\.(stl|obj)$/i, '');
        }

        showToast('File uploaded successfully', 'success');

    } catch (error) {
        // Clear the upload on error
        clearUpload();

        // Show appropriate error message
        if (error.name === 'TypeError' && error.message.includes('fetch')) {
            showToast('Network error. Please check your connection.', 'error');
        } else {
            showToast(error.message || 'Upload failed. Please try again.', 'error');
        }
    } finally {
        // Remove uploading state
        uploadZone.classList.remove('uploading');
    }
}

function clearUpload() {
    uploadedFile = null;
    uploadedFileId = null;

    document.getElementById('file-info').classList.add('hidden');
    document.getElementById('geometry-info').classList.add('hidden');
    document.getElementById('run-btn').disabled = true;

    // Clear 3D viewer
    if (mesh) {
        scene.remove(mesh);
        mesh = null;
    }

    // Show placeholder
    const container = document.getElementById('viewer-container');
    const placeholder = container.querySelector('.viewer-placeholder');
    if (placeholder) placeholder.style.display = 'flex';
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function updateGeometryInfo(info) {
    const geoInfo = document.getElementById('geometry-info');
    geoInfo.classList.remove('hidden');

    document.getElementById('info-triangles').textContent =
        info.triangles ? info.triangles.toLocaleString() : '-';

    if (info.dimensions) {
        const dims = info.dimensions.map(d => d.toFixed(3)).join(' × ');
        document.getElementById('info-dimensions').textContent = dims + ' m';
    }

    if (info.center) {
        const center = info.center.map(c => c.toFixed(3)).join(', ');
        document.getElementById('info-center').textContent = `(${center})`;
    }
}

// 3D Viewer (Three.js)
function initViewer() {
    const container = document.getElementById('viewer-container');
    if (!container) {
        console.error('Viewer container not found');
        return;
    }

    // Ensure container has dimensions (fallback if CSS hasn't applied yet)
    const width = container.clientWidth || 600;
    const height = container.clientHeight || 400;

    // Check if Three.js loaded
    if (typeof THREE === 'undefined') {
        console.error('Three.js not loaded - check CDN connection');
        return;
    }

    // Scene
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x1a1f26);

    // Camera
    camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.set(2, 1.5, 2);

    // Renderer
    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(window.devicePixelRatio);

    // Controls
    controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;

    // Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(5, 5, 5);
    scene.add(directionalLight);

    const backLight = new THREE.DirectionalLight(0xffffff, 0.3);
    backLight.position.set(-5, -5, -5);
    scene.add(backLight);

    // Grid helper
    const gridHelper = new THREE.GridHelper(4, 20, 0x2f3336, 0x2f3336);
    scene.add(gridHelper);

    // Axes helper
    const axesHelper = new THREE.AxesHelper(1);
    scene.add(axesHelper);

    // Animation loop
    function animate() {
        requestAnimationFrame(animate);
        controls.update();
        renderer.render(scene, camera);
    }
    animate();

    // Handle resize
    window.addEventListener('resize', () => {
        const width = container.clientWidth;
        const height = container.clientHeight || 500;
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
        renderer.setSize(width, height);
    });
}

function loadSTLInViewer(file) {
    const container = document.getElementById('viewer-container');

    if (!container) {
        console.error('Viewer container not found');
        return;
    }

    if (!renderer || !scene) {
        console.error('3D viewer not initialized - reinitializing...');
        initViewer();
        if (!renderer || !scene) {
            console.error('Failed to initialize 3D viewer');
            return;
        }
    }

    // Hide placeholder
    const placeholder = container.querySelector('.viewer-placeholder');
    if (placeholder) placeholder.style.display = 'none';

    // Append canvas if not already
    if (!container.querySelector('canvas') && renderer && renderer.domElement) {
        container.appendChild(renderer.domElement);
    }

    // Remove existing mesh
    if (mesh) {
        scene.remove(mesh);
    }

    // Check STLLoader is available
    if (typeof THREE.STLLoader === 'undefined') {
        console.error('STLLoader not loaded - check CDN');
        return;
    }

    // Load STL
    const loader = new THREE.STLLoader();
    const reader = new FileReader();

    reader.onload = (e) => {
        const geometry = loader.parse(e.target.result);

        // Center geometry
        geometry.computeBoundingBox();
        const center = new THREE.Vector3();
        geometry.boundingBox.getCenter(center);
        geometry.translate(-center.x, -center.y, -center.z);

        // Scale to fit view
        const size = new THREE.Vector3();
        geometry.boundingBox.getSize(size);
        const maxDim = Math.max(size.x, size.y, size.z);
        const scale = 1.5 / maxDim;
        geometry.scale(scale, scale, scale);

        // Material
        const material = new THREE.MeshPhongMaterial({
            color: 0x1d9bf0,
            specular: 0x111111,
            shininess: 30,
            flatShading: false
        });

        mesh = new THREE.Mesh(geometry, material);
        scene.add(mesh);

        // Reset camera
        resetCamera();
        console.log('STL loaded successfully:', file.name);
    };

    reader.onerror = (e) => {
        console.error('Error reading file:', e);
    };

    reader.readAsArrayBuffer(file);
}

function resetCamera() {
    camera.position.set(2, 1.5, 2);
    camera.lookAt(0, 0, 0);
    controls.reset();
}

function toggleWireframe() {
    wireframeMode = !wireframeMode;
    if (mesh) {
        mesh.material.wireframe = wireframeMode;
    }
}

// Form
function initForm() {
    const form = document.getElementById('sim-form');
    const speedInput = document.getElementById('speed');

    // Update speed hint function
    function updateSpeedHint() {
        const speed = parseFloat(speedInput.value) || 0;
        const kmh = (speed * 3.6).toFixed(0);
        const mph = (speed * 2.237).toFixed(0);
        document.getElementById('speed-hint').textContent = `≈ ${kmh} km/h / ${mph} mph`;
    }

    // Initialize speed hint on load
    updateSpeedHint();

    // Update on input
    speedInput.addEventListener('input', updateSpeedHint);

    // Toggle rotation method dropdown visibility based on wheel rotation toggle
    const rollingEnabledCheckbox = document.getElementById('rolling-enabled');
    const rotationMethodGroup = document.getElementById('rotation-method-group');

    function updateRotationMethodVisibility() {
        if (rollingEnabledCheckbox.checked) {
            rotationMethodGroup.style.display = 'block';
        } else {
            rotationMethodGroup.style.display = 'none';
        }
    }

    // Initialize visibility
    updateRotationMethodVisibility();

    // Update on toggle change
    rollingEnabledCheckbox.addEventListener('change', updateRotationMethodVisibility);

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        if (!uploadedFileId) {
            showToast('Please upload a file first', 'error');
            return;
        }

        const formData = new FormData();
        formData.append('file_id', uploadedFileId);
        formData.append('name', document.getElementById('sim-name').value);
        formData.append('speed', document.getElementById('speed').value);
        formData.append('yaw_angles', document.getElementById('yaw-angles').value);
        formData.append('ground_enabled', document.getElementById('ground-enabled').checked);
        formData.append('ground_type', document.getElementById('ground-type').value);
        formData.append('rolling_enabled', document.getElementById('rolling-enabled').checked);
        formData.append('wheel_radius', document.getElementById('wheel-radius').value);
        formData.append('quality', document.getElementById('quality').value);
        formData.append('gpu_acceleration', document.getElementById('gpu-acceleration').checked);

        // Only send rotation_method if wheel rotation is enabled
        const rollingEnabled = document.getElementById('rolling-enabled').checked;
        if (rollingEnabled) {
            formData.append('rotation_method', document.getElementById('rotation-method').value);
        } else {
            formData.append('rotation_method', 'none');
        }

        // Check if multiple yaw angles - use batch endpoint
        const yawAnglesStr = document.getElementById('yaw-angles').value;
        const yawAngles = yawAnglesStr.split(',').map(s => s.trim()).filter(s => s);
        const useBatch = yawAngles.length > 1;
        const endpoint = useBatch ? '/api/simulate/batch' : '/api/simulate';

        // Disable submit button during submission
        const submitBtn = document.getElementById('run-btn');
        const originalBtnText = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = useBatch
            ? `<span class="spinner"></span> Starting batch (${yawAngles.length} angles)...`
            : '<span class="spinner"></span> Starting...';

        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                body: formData
            });

            // Handle specific HTTP error codes
            if (!response.ok) {
                let errorMessage = 'Failed to start simulation';
                try {
                    const errorData = await response.json();
                    errorMessage = errorData.detail || errorData.message || errorMessage;
                } catch {
                    if (response.status === 400) {
                        errorMessage = 'Invalid simulation parameters';
                    } else if (response.status === 404) {
                        errorMessage = 'Geometry file not found. Please re-upload.';
                    } else if (response.status === 503) {
                        errorMessage = 'Server busy. Please try again later.';
                    } else if (response.status >= 500) {
                        errorMessage = 'Server error. Please try again later.';
                    }
                }
                throw new Error(errorMessage);
            }

            const data = await response.json();
            if (useBatch) {
                showToast(`Batch started: ${data.batch_id} (${yawAngles.length} yaw angles)`, 'success');
            } else {
                showToast(`Simulation started: ${data.job_id}`, 'success');
            }

            // Switch to jobs view
            document.querySelector('.nav-btn[data-view="jobs"]').click();

        } catch (error) {
            // Show appropriate error message
            if (error.name === 'TypeError' && error.message.includes('fetch')) {
                showToast('Network error. Please check your connection.', 'error');
            } else {
                showToast(error.message || 'Failed to start simulation', 'error');
            }
        } finally {
            // Re-enable submit button
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalBtnText;
        }
    });
}

// Jobs
let jobPollInterval = null;

function pollJobs() {
    // Poll every 5 seconds
    jobPollInterval = setInterval(refreshJobs, 5000);
}

async function refreshJobs() {
    try {
        const response = await fetch('/api/jobs');
        if (!response.ok) return;

        const jobs = await response.json();
        renderJobs(jobs);

    } catch (error) {
        console.error('Failed to fetch jobs:', error);
    }
}

// State for job list
let jobSearchQuery = '';
let jobSortField = 'created_at';
let jobSortDirection = 'desc';

function renderJobs(jobs) {
    const container = document.getElementById('jobs-list');
    const emptyState = document.getElementById('jobs-empty');

    if (jobs.length === 0) {
        // Show the enhanced empty state if it exists
        if (emptyState) {
            emptyState.style.display = 'block';
        } else {
            container.innerHTML = `
                <div class="empty-state">
                    <svg class="empty-state-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <circle cx="12" cy="12" r="10"/>
                        <polyline points="12 6 12 12 16 14"/>
                    </svg>
                    <h3>No simulations yet</h3>
                    <p>Upload a wheel geometry and configure your simulation to get started.</p>
                    <button class="btn-cta" onclick="showView('upload')">Upload Geometry</button>
                </div>
            `;
        }
        return;
    }

    // Hide empty state if jobs exist
    if (emptyState) {
        emptyState.style.display = 'none';
    }

    // Filter by search query
    let filteredJobs = jobs;
    if (jobSearchQuery) {
        const query = jobSearchQuery.toLowerCase();
        filteredJobs = jobs.filter(job =>
            job.name.toLowerCase().includes(query) ||
            job.id.toLowerCase().includes(query)
        );
    }

    // Sort jobs
    filteredJobs.sort((a, b) => {
        let aVal, bVal;
        switch (jobSortField) {
            case 'name':
                aVal = a.name.toLowerCase();
                bVal = b.name.toLowerCase();
                break;
            case 'status':
                aVal = a.status;
                bVal = b.status;
                break;
            case 'created_at':
            default:
                aVal = new Date(a.created_at);
                bVal = new Date(b.created_at);
        }
        if (aVal < bVal) return jobSortDirection === 'asc' ? -1 : 1;
        if (aVal > bVal) return jobSortDirection === 'asc' ? 1 : -1;
        return 0;
    });

    // Render table view
    container.innerHTML = `
        <div class="jobs-header">
            <div class="jobs-search">
                <input type="text"
                       placeholder="Search simulations..."
                       value="${jobSearchQuery}"
                       oninput="filterJobs(this.value)">
            </div>
        </div>

        <table class="jobs-table">
            <thead>
                <tr>
                    <th onclick="sortJobs('name')">
                        Name
                        ${jobSortField === 'name' ? `<span class="sort-icon">${jobSortDirection === 'asc' ? '↑' : '↓'}</span>` : ''}
                    </th>
                    <th>Quality</th>
                    <th onclick="sortJobs('status')">
                        Status
                        ${jobSortField === 'status' ? `<span class="sort-icon">${jobSortDirection === 'asc' ? '↑' : '↓'}</span>` : ''}
                    </th>
                    <th>Yaw Angles</th>
                    <th onclick="sortJobs('created_at')">
                        Created
                        ${jobSortField === 'created_at' ? `<span class="sort-icon">${jobSortDirection === 'asc' ? '↑' : '↓'}</span>` : ''}
                    </th>
                    <th></th>
                </tr>
            </thead>
            <tbody>
                ${filteredJobs.map(job => renderJobRow(job)).join('')}
            </tbody>
        </table>

        ${filteredJobs.length === 0 && jobSearchQuery ? `
            <div class="empty-state" style="padding: 2rem;">
                <p>No simulations match "${jobSearchQuery}"</p>
                <button class="btn-secondary" onclick="filterJobs('')">Clear search</button>
            </div>
        ` : ''}
    `;
}

function renderJobRow(job) {
    const config = job.config || {};
    const quality = config.quality || 'standard';
    const yawAngles = config.yaw_angles || [];

    return `
        <tr onclick="showJobResults('${job.id}')">
            <td>
                <div class="job-name-cell">
                    <strong>${job.name}</strong>
                    <span style="font-size: 0.75rem; color: var(--text-secondary); display: block;">
                        ${config.speed ? config.speed + ' m/s' : ''}
                    </span>
                </div>
            </td>
            <td>
                <span class="quality-badge ${quality}">${quality.toUpperCase()}</span>
            </td>
            <td>
                <span class="status-dot ${job.status}">${formatStatus(job.status)}</span>
                ${job.status !== 'complete' && job.status !== 'failed' ? `
                    <div class="job-progress" style="margin-top: 4px;">
                        <div class="job-progress-bar" style="width: ${job.progress}%"></div>
                    </div>
                ` : ''}
            </td>
            <td>
                <div class="yaw-angles-list">
                    ${yawAngles.slice(0, 3).map(yaw => `<span class="yaw-chip">${yaw}°</span>`).join('')}
                    ${yawAngles.length > 3 ? `<span class="yaw-chip">+${yawAngles.length - 3}</span>` : ''}
                </div>
            </td>
            <td>${formatDate(job.created_at)}</td>
            <td>
                <button class="btn-delete" onclick="event.stopPropagation(); deleteJob('${job.id}')" title="Delete">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"/>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    </svg>
                </button>
            </td>
        </tr>
    `;
}

function formatStatus(status) {
    const statusMap = {
        'queued': 'Queued',
        'preparing': 'Preparing',
        'meshing': 'Meshing',
        'solving': 'Solving',
        'post-processing': 'Post-processing',
        'complete': 'Completed',
        'failed': 'Failed'
    };
    return statusMap[status] || status;
}

function filterJobs(query) {
    jobSearchQuery = query;
    refreshJobs();
}

function sortJobs(field) {
    if (jobSortField === field) {
        // Toggle direction
        jobSortDirection = jobSortDirection === 'asc' ? 'desc' : 'asc';
    } else {
        jobSortField = field;
        jobSortDirection = field === 'created_at' ? 'desc' : 'asc';
    }
    refreshJobs();
}

async function deleteJob(jobId) {
    if (!confirm('Are you sure you want to delete this simulation?')) {
        return;
    }

    try {
        const response = await fetch(`/api/jobs/${jobId}`, { method: 'DELETE' });
        if (response.ok) {
            showToast('Simulation deleted', 'success');
            refreshJobs();
        } else {
            const error = await response.json();
            showToast(error.detail || 'Failed to delete simulation', 'error');
        }
    } catch (error) {
        showToast('Failed to delete simulation', 'error');
    }
}

// Make new functions globally available
window.filterJobs = filterJobs;
window.sortJobs = sortJobs;
window.deleteJob = deleteJob;

function formatDate(dateStr) {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;

    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;

    return date.toLocaleDateString();
}

async function showJobResults(jobId) {
    try {
        const response = await fetch(`/api/jobs/${jobId}`);
        if (!response.ok) throw new Error('Failed to fetch job');

        const job = await response.json();

        // Switch to results view
        document.querySelector('.nav-btn[data-view="results"]').click();

        // Render results
        renderResults(job);

    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    }
}

// Current metric view for results display
let currentMetricType = 'force';
let currentJobData = null;

function renderResults(job) {
    const container = document.getElementById('results-content');
    currentJobData = job;

    if (job.status !== 'complete') {
        container.innerHTML = `
            <div class="results-in-progress">
                <div class="progress-indicator">
                    <div class="progress-spinner"></div>
                    <div class="progress-info">
                        <h3>Simulation ${job.status}</h3>
                        <div class="progress-bar-container">
                            <div class="progress-bar" style="width: ${job.progress}%"></div>
                        </div>
                        <span class="progress-text">${job.progress}% complete</span>
                    </div>
                </div>
                ${job.error ? `<div class="error-message"><strong>Error:</strong> ${job.error}</div>` : ''}
            </div>
        `;
        return;
    }

    const results = job.results || {};
    const forces = results.forces || {};
    const coefficients = results.coefficients || {};
    const config = job.config || {};

    // Calculate side force from yaw angle (approximation)
    const yawAngle = config.yaw_angles?.[0] || 0;
    const sideForce = (forces.lift_N || 0) * Math.sin(yawAngle * Math.PI / 180);

    container.innerHTML = `
        <div class="results-dashboard">
            <!-- Header with simulation name and status -->
            <div class="results-header">
                <div class="results-title">
                    <h2>${job.name}</h2>
                    <span class="status-badge completed">Completed</span>
                </div>
                <div class="results-actions">
                    <button class="btn-secondary" onclick="exportResultsPDF('${job.id}')">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                            <polyline points="7 10 12 15 17 10"/>
                            <line x1="12" y1="15" x2="12" y2="3"/>
                        </svg>
                        Export PDF
                    </button>
                </div>
            </div>

            <!-- Two-column layout -->
            <div class="results-layout">
                <!-- Left: Key Metrics -->
                <div class="results-main">
                    <!-- Metric Type Tabs -->
                    <div class="metric-tabs">
                        <button class="metric-tab ${currentMetricType === 'force' ? 'active' : ''}" onclick="switchMetricType('force')">Force</button>
                        <button class="metric-tab ${currentMetricType === 'coefficient' ? 'active' : ''}" onclick="switchMetricType('coefficient')">Coefficient</button>
                        <button class="metric-tab ${currentMetricType === 'cda' ? 'active' : ''}" onclick="switchMetricType('cda')">CdA</button>
                        <button class="metric-tab ${currentMetricType === 'moment' ? 'active' : ''}" onclick="switchMetricType('moment')">Moment</button>
                    </div>

                    <!-- Metrics Table -->
                    <div class="metrics-table-container" id="metrics-display">
                        ${renderMetricsTable(job, currentMetricType)}
                    </div>

                    <!-- Yaw Angle Selector (if multiple) -->
                    ${config.yaw_angles && config.yaw_angles.length > 1 ? `
                    <div class="yaw-selector">
                        <label>Yaw Angle:</label>
                        <select id="yaw-select" onchange="updateYawDisplay()">
                            ${config.yaw_angles.map((yaw, i) =>
                                `<option value="${i}">${yaw}°</option>`
                            ).join('')}
                        </select>
                    </div>
                    ` : ''}
                </div>

                <!-- Right: Input Parameters -->
                <div class="results-sidebar">
                    <div class="params-card">
                        <h3>Input Parameters</h3>
                        <div class="params-list">
                            <div class="param-item">
                                <span class="param-label">Quality</span>
                                <span class="param-value">
                                    <span class="quality-badge ${config.quality}">${config.quality?.toUpperCase() || 'STANDARD'}</span>
                                </span>
                            </div>
                            <div class="param-item">
                                <span class="param-label">Speed</span>
                                <span class="param-value">${config.speed} m/s</span>
                            </div>
                            <div class="param-item">
                                <span class="param-label">Yaw Angles</span>
                                <span class="param-value">${config.yaw_angles?.join('°, ')}°</span>
                            </div>
                            <div class="param-item">
                                <span class="param-label">Ground</span>
                                <span class="param-value">${config.ground_enabled ? config.ground_type : 'Disabled'}</span>
                            </div>
                            <div class="param-item">
                                <span class="param-label">Wheel Rotation</span>
                                <span class="param-value">${config.rolling_enabled ? 'Enabled' : 'Disabled'}</span>
                            </div>
                            <div class="param-item">
                                <span class="param-label">Wheel Radius</span>
                                <span class="param-value">${config.wheel_radius} m</span>
                            </div>
                            <div class="param-item">
                                <span class="param-label">Reynolds Number</span>
                                <span class="param-value">${config.reynolds ? (config.reynolds / 1000).toFixed(1) + 'k' : '-'}</span>
                            </div>
                            <div class="param-item">
                                <span class="param-label">Reference Area</span>
                                <span class="param-value">${results.aref ? (results.aref * 10000).toFixed(2) + ' cm²' : '-'}</span>
                            </div>
                        </div>
                    </div>

                    <!-- Simulation Info -->
                    <div class="params-card">
                        <h3>Simulation Info</h3>
                        <div class="params-list">
                            <div class="param-item">
                                <span class="param-label">Job ID</span>
                                <span class="param-value mono">${job.id}</span>
                            </div>
                            <div class="param-item">
                                <span class="param-label">Created</span>
                                <span class="param-value">${formatDateTime(job.created_at)}</span>
                            </div>
                            <div class="param-item">
                                <span class="param-label">Completed</span>
                                <span class="param-value">${formatDateTime(job.updated_at)}</span>
                            </div>
                            <div class="param-item">
                                <span class="param-label">Converged</span>
                                <span class="param-value">${results.converged ? '✓ Yes' : '✗ No'}</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Visualization Section -->
            <div class="visualization-section">
                <!-- Coefficient History -->
                <div class="chart-card">
                    <div class="chart-header">
                        <h3>Coefficient Evolution</h3>
                        <select id="force-type-select" onchange="changeForceType(this.value)">
                            <option value="drag">Drag (Cd)</option>
                            <option value="lift">Lift (Cl)</option>
                            <option value="side">Front Lift (Cl_f)</option>
                        </select>
                    </div>
                    <div class="chart-container" id="force-distribution-chart">
                        <div class="chart-loading">Loading...</div>
                    </div>
                </div>

                <!-- Convergence History -->
                <div class="chart-card">
                    <div class="chart-header">
                        <h3>All Coefficients</h3>
                    </div>
                    <div class="chart-container" id="convergence-chart">
                        <div class="chart-loading">Loading...</div>
                    </div>
                </div>
            </div>

            <!-- Pressure Slice Visualization -->
            <div class="slice-viewer" id="slice-viewer">
                <div class="slice-viewer-header">
                    <h3>Pressure Slices</h3>
                    <button class="btn-icon" onclick="toggleSliceFullscreen()" title="Toggle fullscreen">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M8 3H5a2 2 0 0 0-2 2v3"/>
                            <path d="M21 8V5a2 2 0 0 0-2-2h-3"/>
                            <path d="M3 16v3a2 2 0 0 0 2 2h3"/>
                            <path d="M16 21h3a2 2 0 0 0 2-2v-3"/>
                        </svg>
                    </button>
                </div>
                <div class="slice-viewer-content">
                    <div class="slice-display" id="slice-display">
                        <div class="slice-placeholder">
                            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
                                <rect x="3" y="3" width="18" height="18" rx="2"/>
                                <line x1="3" y1="9" x2="21" y2="9"/>
                                <line x1="3" y1="15" x2="21" y2="15"/>
                                <line x1="9" y1="3" x2="9" y2="21"/>
                                <line x1="15" y1="3" x2="15" y2="21"/>
                            </svg>
                            <p>Pressure slice visualization</p>
                            <small>Slice data will appear here when available</small>
                        </div>
                    </div>
                    <div class="slice-controls">
                        <div class="slice-control-group">
                            <label>Slice Position</label>
                            <div class="slice-info" id="slice-info">Slice [1 / 1]</div>
                            <input type="range" class="slice-slider" id="slice-slider"
                                   min="0" max="48" value="24"
                                   oninput="updateSlicePosition(this.value)">
                            <div class="slice-nav-buttons">
                                <button onclick="prevSlice()">← Previous</button>
                                <button onclick="nextSlice()">Next →</button>
                            </div>
                        </div>

                        <div class="slice-control-group">
                            <label>Direction</label>
                            <div class="direction-buttons">
                                <button class="active" onclick="setSliceDirection('x')" id="dir-x">X</button>
                                <button onclick="setSliceDirection('y')" id="dir-y">Y</button>
                                <button onclick="setSliceDirection('z')" id="dir-z">Z</button>
                            </div>
                        </div>

                        <div class="slice-control-group">
                            <label>Field</label>
                            <select id="slice-field-select" onchange="updateSliceField(this.value)">
                                <option value="Cp">Total Pressure Coefficient</option>
                                <option value="p">Static Pressure</option>
                                <option value="U">Velocity Magnitude</option>
                            </select>
                        </div>

                        <div class="slice-control-group">
                            <label>Color Scale</label>
                            <div class="color-scale">
                                <div class="color-scale-bar"></div>
                                <div class="color-scale-labels">
                                    <span>-0.60</span>
                                    <span>0.20</span>
                                    <span>1.00</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Load charts and slice viewer after DOM is updated
    setTimeout(() => {
        renderForceDistributionChart(job.id, 'force-distribution-chart', 'drag');
        renderConvergenceChart(job.id, 'convergence-chart');
        initSliceViewer(job.id);
    }, 100);
}

function renderMetricsTable(job, metricType) {
    const results = job.results || {};
    const forces = results.forces || {};
    const coefficients = results.coefficients || {};
    const config = job.config || {};
    const yawAngle = config.yaw_angles?.[0] || 0;

    // Calculate derived values
    const rho = config.air?.rho || 1.225;
    const U = config.speed || 13.9;
    const A = results.aref || 0.0225;
    const q = 0.5 * rho * U * U;
    const lRef = (config.wheel_radius || 0.325) * 2;

    switch (metricType) {
        case 'force':
            return `
                <table class="metrics-table">
                    <thead>
                        <tr>
                            <th>Yaw</th>
                            <th>Fd (Drag)</th>
                            <th>Fl (Lift)</th>
                            <th>Fs (Side)</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>${yawAngle}°</td>
                            <td class="metric-value">${(forces.drag_N || 0).toFixed(3)} <span class="unit">N</span></td>
                            <td class="metric-value">${(forces.lift_N || 0).toFixed(3)} <span class="unit">N</span></td>
                            <td class="metric-value">${(forces.side_N || (forces.lift_N || 0) * Math.sin(yawAngle * Math.PI / 180)).toFixed(3)} <span class="unit">N</span></td>
                        </tr>
                    </tbody>
                </table>
            `;
        case 'coefficient':
            const Cs = (coefficients.Cl || 0) * Math.sin(yawAngle * Math.PI / 180);
            return `
                <table class="metrics-table">
                    <thead>
                        <tr>
                            <th>Yaw</th>
                            <th>Cd</th>
                            <th>Cl</th>
                            <th>Cs</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>${yawAngle}°</td>
                            <td class="metric-value">${(coefficients.Cd || 0).toFixed(4)}</td>
                            <td class="metric-value">${(coefficients.Cl || 0).toFixed(4)}</td>
                            <td class="metric-value">${Cs.toFixed(4)}</td>
                        </tr>
                    </tbody>
                </table>
            `;
        case 'cda':
            const CdA = (results.CdA || 0) * 10000; // Convert to cm²
            const ClA = (coefficients.Cl || 0) * A * 10000;
            const CsA = ClA * Math.sin(yawAngle * Math.PI / 180);
            return `
                <table class="metrics-table">
                    <thead>
                        <tr>
                            <th>Yaw</th>
                            <th>CdA</th>
                            <th>ClA</th>
                            <th>CsA</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>${yawAngle}°</td>
                            <td class="metric-value">${CdA.toFixed(2)} <span class="unit">cm²</span></td>
                            <td class="metric-value">${ClA.toFixed(2)} <span class="unit">cm²</span></td>
                            <td class="metric-value">${CsA.toFixed(2)} <span class="unit">cm²</span></td>
                        </tr>
                    </tbody>
                </table>
            `;
        case 'moment':
            const Cm = coefficients.Cm || 0;
            const MomentN = Cm * q * A * lRef;
            return `
                <table class="metrics-table">
                    <thead>
                        <tr>
                            <th>Yaw</th>
                            <th>Cm</th>
                            <th>Moment</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>${yawAngle}°</td>
                            <td class="metric-value">${Cm.toFixed(4)}</td>
                            <td class="metric-value">${MomentN.toFixed(4)} <span class="unit">Nm</span></td>
                        </tr>
                    </tbody>
                </table>
            `;
        default:
            return '<p>Select a metric type</p>';
    }
}

function switchMetricType(type) {
    currentMetricType = type;

    // Update tab styling
    document.querySelectorAll('.metric-tab').forEach(tab => {
        tab.classList.toggle('active', tab.textContent.toLowerCase() === type);
    });

    // Re-render metrics table
    if (currentJobData) {
        document.getElementById('metrics-display').innerHTML =
            renderMetricsTable(currentJobData, type);
    }
}

function formatDateTime(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleString();
}

function exportResultsPDF(jobId) {
    showToast('PDF export coming soon', 'info');
}

// Make new functions globally available
window.switchMetricType = switchMetricType;
window.exportResultsPDF = exportResultsPDF;

// =============================================================================
// Visualization Charts (Phase 3 - US-003, US-004)
// =============================================================================

// Chart instances
let convergenceChart = null;
let forceDistributionChart = null;

/**
 * Render convergence history chart showing coefficient values over iterations
 */
async function renderConvergenceChart(jobId, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    try {
        const response = await fetch(`/api/jobs/${jobId}/convergence`);
        if (!response.ok) {
            container.innerHTML = '<p class="chart-error">Convergence data not available</p>';
            return;
        }

        const data = await response.json();

        if (!data.time || data.time.length === 0) {
            container.innerHTML = '<p class="chart-error">No convergence data found</p>';
            return;
        }

        // Create canvas
        container.innerHTML = '<canvas id="convergence-canvas"></canvas>';
        const canvas = document.getElementById('convergence-canvas');
        const ctx = canvas.getContext('2d');

        // Destroy existing chart
        if (convergenceChart) {
            convergenceChart.destroy();
        }

        // Create new chart
        convergenceChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.time,
                datasets: [
                    {
                        label: 'Cd (Drag)',
                        data: data.Cd,
                        borderColor: '#1d9bf0',
                        backgroundColor: 'rgba(29, 155, 240, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.3,
                        pointRadius: 0
                    },
                    {
                        label: 'Cl (Lift)',
                        data: data.Cl,
                        borderColor: '#00ba7c',
                        backgroundColor: 'rgba(0, 186, 124, 0.1)',
                        borderWidth: 2,
                        fill: false,
                        tension: 0.3,
                        pointRadius: 0
                    },
                    {
                        label: 'Cm (Moment)',
                        data: data.Cm,
                        borderColor: '#ffad1f',
                        backgroundColor: 'rgba(255, 173, 31, 0.1)',
                        borderWidth: 2,
                        fill: false,
                        tension: 0.3,
                        pointRadius: 0
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            color: '#e7e9ea',
                            usePointStyle: true
                        }
                    },
                    tooltip: {
                        backgroundColor: '#242b33',
                        titleColor: '#e7e9ea',
                        bodyColor: '#e7e9ea',
                        borderColor: '#2f3336',
                        borderWidth: 1
                    }
                },
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: 'Iteration',
                            color: '#8b98a5'
                        },
                        ticks: { color: '#8b98a5' },
                        grid: { color: '#2f3336' }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Coefficient',
                            color: '#8b98a5'
                        },
                        ticks: { color: '#8b98a5' },
                        grid: { color: '#2f3336' }
                    }
                }
            }
        });

    } catch (error) {
        container.innerHTML = `<p class="chart-error">Error loading convergence data: ${error.message}</p>`;
    }
}

/**
 * Render force coefficient history chart
 * Shows Cd, Cl, Cm evolution over simulation iterations
 */
async function renderForceDistributionChart(jobId, containerId, forceType = 'drag') {
    const container = document.getElementById(containerId);
    if (!container) return;

    try {
        const response = await fetch(`/api/jobs/${jobId}/viz/force_distribution`);
        if (!response.ok) {
            container.innerHTML = '<p class="chart-error">Force data not available</p>';
            return;
        }

        const data = await response.json();

        if (!data.time || data.time.length === 0) {
            container.innerHTML = `
                <div class="chart-placeholder">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M3 3v18h18"/>
                        <path d="M18 17l-5-10-5 10"/>
                    </svg>
                    <p>Force data will be available after simulation completes</p>
                </div>
            `;
            return;
        }

        // Create canvas
        container.innerHTML = '<canvas id="force-dist-canvas"></canvas>';
        const canvas = document.getElementById('force-dist-canvas');
        const ctx = canvas.getContext('2d');

        // Destroy existing chart
        if (forceDistributionChart) {
            forceDistributionChart.destroy();
        }

        // Select data based on force type
        let forceData, label, color;
        switch (forceType) {
            case 'lift':
                forceData = data.Cl || [];
                label = 'Lift Coefficient (Cl)';
                color = '#00ba7c';
                break;
            case 'side':
                // Side force coefficient computed from lift and yaw
                forceData = data.Cl_front || data.Cl || [];
                label = 'Front Lift (Cl_f)';
                color = '#ffad1f';
                break;
            case 'drag':
            default:
                forceData = data.Cd || [];
                label = 'Drag Coefficient (Cd)';
                color = '#1d9bf0';
        }

        // Create chart
        forceDistributionChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.time,
                datasets: [{
                    label: label,
                    data: forceData,
                    borderColor: color,
                    backgroundColor: color + '33',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            color: '#e7e9ea',
                            usePointStyle: true
                        }
                    },
                    tooltip: {
                        backgroundColor: '#242b33',
                        titleColor: '#e7e9ea',
                        bodyColor: '#e7e9ea',
                        borderColor: '#2f3336',
                        borderWidth: 1,
                        callbacks: {
                            title: (items) => `Iteration ${items[0].label}`,
                            label: (context) => `${context.dataset.label}: ${context.parsed.y.toFixed(4)}`
                        }
                    }
                },
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: 'Iteration',
                            color: '#8b98a5'
                        },
                        ticks: {
                            color: '#8b98a5',
                            maxTicksLimit: 10
                        },
                        grid: { color: '#2f3336' }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Coefficient',
                            color: '#8b98a5'
                        },
                        ticks: { color: '#8b98a5' },
                        grid: { color: '#2f3336' }
                    }
                }
            }
        });

    } catch (error) {
        container.innerHTML = `<p class="chart-error">Error loading force data: ${error.message}</p>`;
    }
}

/**
 * Change force type in force distribution chart
 */
function changeForceType(forceType) {
    if (currentJobData) {
        renderForceDistributionChart(currentJobData.id, 'force-distribution-chart', forceType);
    }
}

// Make chart functions globally available
window.renderConvergenceChart = renderConvergenceChart;
window.renderForceDistributionChart = renderForceDistributionChart;
window.changeForceType = changeForceType;

// =============================================================================
// Pressure Slice Viewer (US-004)
// =============================================================================

// Slice viewer state
let sliceState = {
    direction: 'x',
    field: 'Cp',
    currentIndex: 24,
    maxIndex: 48,
    slices: [],
    jobId: null
};

/**
 * Initialize slice viewer for a job
 */
async function initSliceViewer(jobId) {
    sliceState.jobId = jobId;

    try {
        const response = await fetch(`/api/jobs/${jobId}/viz/slices`);
        if (!response.ok) {
            showSlicePlaceholder('Slice data not available');
            return;
        }

        const data = await response.json();

        if (!data.slices || data.slices.length === 0) {
            showSlicePlaceholder(data.note || 'No pressure slices generated');
            return;
        }

        sliceState.slices = data.slices;
        sliceState.maxIndex = data.slices.length - 1;

        // Update slider
        const slider = document.getElementById('slice-slider');
        if (slider) {
            slider.max = sliceState.maxIndex;
            slider.value = Math.floor(sliceState.maxIndex / 2);
            sliceState.currentIndex = parseInt(slider.value);
        }

        updateSliceDisplay();

    } catch (error) {
        showSlicePlaceholder('Error loading slice data');
    }
}

/**
 * Show placeholder message in slice display
 */
function showSlicePlaceholder(message) {
    const display = document.getElementById('slice-display');
    if (display) {
        display.innerHTML = `
            <div class="slice-placeholder">
                <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
                    <rect x="3" y="3" width="18" height="18" rx="2"/>
                    <line x1="3" y1="9" x2="21" y2="9"/>
                    <line x1="3" y1="15" x2="21" y2="15"/>
                </svg>
                <p>${message}</p>
                <small>Configure pressure slices in OpenFOAM postProcessing</small>
            </div>
        `;
    }
}

/**
 * Update slice position from slider
 */
function updateSlicePosition(value) {
    sliceState.currentIndex = parseInt(value);
    updateSliceDisplay();
}

/**
 * Navigate to previous slice
 */
function prevSlice() {
    if (sliceState.currentIndex > 0) {
        sliceState.currentIndex--;
        const slider = document.getElementById('slice-slider');
        if (slider) slider.value = sliceState.currentIndex;
        updateSliceDisplay();
    }
}

/**
 * Navigate to next slice
 */
function nextSlice() {
    if (sliceState.currentIndex < sliceState.maxIndex) {
        sliceState.currentIndex++;
        const slider = document.getElementById('slice-slider');
        if (slider) slider.value = sliceState.currentIndex;
        updateSliceDisplay();
    }
}

/**
 * Set slice direction (x, y, z)
 */
function setSliceDirection(direction) {
    sliceState.direction = direction;

    // Update button states
    document.querySelectorAll('.direction-buttons button').forEach(btn => {
        btn.classList.toggle('active', btn.id === `dir-${direction}`);
    });

    updateSliceDisplay();
}

/**
 * Update slice field type
 */
function updateSliceField(field) {
    sliceState.field = field;
    updateSliceDisplay();
}

/**
 * Update the slice display based on current state
 */
function updateSliceDisplay() {
    const display = document.getElementById('slice-display');
    const info = document.getElementById('slice-info');

    if (info) {
        info.textContent = `Slice [${sliceState.currentIndex + 1} / ${sliceState.maxIndex + 1}]`;
    }

    if (!sliceState.jobId || sliceState.slices.length === 0) {
        return;
    }

    // Filter slices by direction
    const directionSlices = sliceState.slices.filter(s =>
        s.direction === sliceState.direction
    );

    if (directionSlices.length === 0) {
        showSlicePlaceholder(`No ${sliceState.direction.toUpperCase()}-direction slices available`);
        return;
    }

    // Get current slice
    const sliceIndex = Math.min(sliceState.currentIndex, directionSlices.length - 1);
    const slice = directionSlices[sliceIndex];

    if (slice && slice.image_url) {
        display.innerHTML = `<img src="${slice.image_url}" alt="Pressure slice ${sliceState.direction}=${slice.position}">`;
    } else {
        // Show placeholder with position info
        display.innerHTML = `
            <div class="slice-placeholder">
                <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
                    <rect x="3" y="3" width="18" height="18" rx="2"/>
                    <circle cx="12" cy="12" r="4"/>
                </svg>
                <p>Slice ${sliceState.direction.toUpperCase()} = ${slice?.position?.toFixed(3) || '0.000'} m</p>
                <small>Image rendering requires OpenFOAM post-processing</small>
            </div>
        `;
    }
}

/**
 * Toggle fullscreen mode for slice viewer
 */
function toggleSliceFullscreen() {
    const viewer = document.getElementById('slice-viewer');
    if (viewer) {
        viewer.classList.toggle('fullscreen');
    }
}

/**
 * Handle keyboard shortcuts for slice navigation
 */
document.addEventListener('keydown', (e) => {
    // Only handle when slice viewer is visible
    const viewer = document.getElementById('slice-viewer');
    if (!viewer || viewer.offsetParent === null) return;

    switch (e.key) {
        case 'ArrowLeft':
            prevSlice();
            break;
        case 'ArrowRight':
            nextSlice();
            break;
        case 'x':
        case 'X':
            setSliceDirection('x');
            break;
        case 'y':
        case 'Y':
            setSliceDirection('y');
            break;
        case 'z':
        case 'Z':
            setSliceDirection('z');
            break;
        case 'Escape':
            if (viewer.classList.contains('fullscreen')) {
                toggleSliceFullscreen();
            }
            break;
    }
});

// Make slice functions globally available
window.updateSlicePosition = updateSlicePosition;
window.prevSlice = prevSlice;
window.nextSlice = nextSlice;
window.setSliceDirection = setSliceDirection;
window.updateSliceField = updateSliceField;
window.toggleSliceFullscreen = toggleSliceFullscreen;
window.initSliceViewer = initSliceViewer;

// Toast
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type}`;

    // Longer timeout for errors and warnings
    const timeout = (type === 'error' || type === 'warning') ? 5000 : 3000;

    setTimeout(() => {
        toast.classList.add('hidden');
    }, timeout);
}

// Global error handler for uncaught errors
window.addEventListener('error', (event) => {
    console.error('Uncaught error:', event.error);
    // Don't show toast for script errors from CDN or minor issues
    if (event.message && !event.message.includes('Script error')) {
        showToast('An unexpected error occurred', 'error');
    }
});

// Global handler for unhandled promise rejections
window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled promise rejection:', event.reason);
    showToast('An unexpected error occurred', 'error');
    event.preventDefault();
});

// =============================================================================
// Compare Simulations (Phase 4 - US-005)
// =============================================================================

// State for comparison
let compareSelectedJobs = [];
let compareAllJobs = [];
let compareSearchQuery = '';
let compareSortField = 'Cd';
let compareSortDirection = 'asc';

/**
 * Load jobs for comparison selection
 */
async function loadCompareJobs() {
    try {
        const response = await fetch('/api/jobs');
        if (!response.ok) return;

        compareAllJobs = await response.json();

        // Filter to only completed jobs with results
        compareAllJobs = compareAllJobs.filter(j => j.status === 'complete' && j.results);

        // Populate yaw angle filter
        populateYawFilter();

        renderCompareJobList();
    } catch (error) {
        console.error('Failed to load jobs for comparison:', error);
    }
}

/**
 * Populate the yaw angle filter dropdown
 */
function populateYawFilter() {
    const select = document.getElementById('compare-yaw-filter');
    if (!select) return;

    const yawAngles = new Set();
    compareAllJobs.forEach(job => {
        const angles = job.config?.yaw_angles || [];
        angles.forEach(a => yawAngles.add(a));
    });

    // Keep the "All" option, remove others
    select.innerHTML = '<option value="">All yaw angles</option>';

    [...yawAngles].sort((a, b) => a - b).forEach(yaw => {
        const option = document.createElement('option');
        option.value = yaw;
        option.textContent = `${yaw}°`;
        select.appendChild(option);
    });
}

/**
 * Filter jobs in comparison view
 */
function filterCompareJobs(searchValue) {
    if (searchValue !== undefined) {
        compareSearchQuery = searchValue;
    }
    renderCompareJobList();
}

/**
 * Render the job selection list for comparison
 */
function renderCompareJobList() {
    const container = document.getElementById('compare-job-list');
    if (!container) return;

    const searchQuery = compareSearchQuery.toLowerCase();
    const qualityFilter = document.getElementById('compare-quality-filter')?.value || '';
    const yawFilter = document.getElementById('compare-yaw-filter')?.value || '';

    let filteredJobs = compareAllJobs.filter(job => {
        // Search filter
        if (searchQuery && !job.name.toLowerCase().includes(searchQuery)) {
            return false;
        }
        // Quality filter
        if (qualityFilter && job.config?.quality !== qualityFilter) {
            return false;
        }
        // Yaw angle filter
        if (yawFilter) {
            const yawAngle = parseFloat(yawFilter);
            const jobAngles = job.config?.yaw_angles || [];
            if (!jobAngles.includes(yawAngle)) {
                return false;
            }
        }
        return true;
    });

    if (filteredJobs.length === 0) {
        container.innerHTML = `
            <div class="compare-empty">
                <p>No completed simulations found.</p>
                ${compareAllJobs.length === 0 ?
                    '<button class="btn-secondary" onclick="showView(\'upload\')">Run a simulation first</button>' :
                    '<button class="btn-secondary" onclick="clearCompareFilters()">Clear filters</button>'}
            </div>
        `;
        return;
    }

    container.innerHTML = filteredJobs.map(job => {
        const isSelected = compareSelectedJobs.includes(job.id);
        const config = job.config || {};
        const results = job.results || {};
        const coefficients = results.coefficients || {};

        return `
            <div class="compare-job-item ${isSelected ? 'selected' : ''}" onclick="toggleCompareJob('${job.id}')">
                <input type="checkbox" ${isSelected ? 'checked' : ''} onclick="event.stopPropagation(); toggleCompareJob('${job.id}')">
                <div class="compare-job-info">
                    <strong>${job.name}</strong>
                    <span class="compare-job-meta">
                        ${config.speed} m/s | ${config.yaw_angles?.join('°, ')}°
                    </span>
                </div>
                <span class="quality-badge ${config.quality}">${config.quality?.toUpperCase()}</span>
            </div>
        `;
    }).join('');
}

/**
 * Clear comparison filters
 */
function clearCompareFilters() {
    document.getElementById('compare-search').value = '';
    document.getElementById('compare-quality-filter').value = '';
    document.getElementById('compare-yaw-filter').value = '';
    compareSearchQuery = '';
    renderCompareJobList();
}

/**
 * Toggle job selection for comparison
 */
function toggleCompareJob(jobId) {
    const index = compareSelectedJobs.indexOf(jobId);
    if (index === -1) {
        compareSelectedJobs.push(jobId);
    } else {
        compareSelectedJobs.splice(index, 1);
    }

    // Update UI
    renderCompareJobList();
    updateComparisonTable();

    // Enable/disable clear button
    const clearBtn = document.getElementById('clear-compare-btn');
    if (clearBtn) {
        clearBtn.disabled = compareSelectedJobs.length === 0;
    }
}

/**
 * Clear all comparison selections
 */
function clearComparison() {
    compareSelectedJobs = [];
    renderCompareJobList();
    updateComparisonTable();

    const clearBtn = document.getElementById('clear-compare-btn');
    if (clearBtn) clearBtn.disabled = true;
}

/**
 * Update the comparison results table
 */
function updateComparisonTable() {
    const container = document.getElementById('compare-table-container');
    if (!container) return;

    if (compareSelectedJobs.length < 2) {
        container.innerHTML = `
            <div class="empty-state">
                <svg class="empty-state-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <rect x="3" y="3" width="7" height="7"/>
                    <rect x="14" y="3" width="7" height="7"/>
                    <rect x="14" y="14" width="7" height="7"/>
                    <rect x="3" y="14" width="7" height="7"/>
                </svg>
                <h3>Select simulations to compare</h3>
                <p>${compareSelectedJobs.length === 1 ? 'Select at least 1 more simulation.' : 'Check 2 or more simulations from the list.'}</p>
            </div>
        `;
        return;
    }

    // Get selected job data
    const selectedJobData = compareSelectedJobs.map(id =>
        compareAllJobs.find(j => j.id === id)
    ).filter(Boolean);

    // Sort by current sort field
    selectedJobData.sort((a, b) => {
        let aVal, bVal;
        const aResults = a.results || {};
        const bResults = b.results || {};
        const aCoef = aResults.coefficients || {};
        const bCoef = bResults.coefficients || {};
        const aForces = aResults.forces || {};
        const bForces = bResults.forces || {};

        switch (compareSortField) {
            case 'name':
                aVal = a.name.toLowerCase();
                bVal = b.name.toLowerCase();
                break;
            case 'Cd':
                aVal = aCoef.Cd || 0;
                bVal = bCoef.Cd || 0;
                break;
            case 'Cl':
                aVal = aCoef.Cl || 0;
                bVal = bCoef.Cl || 0;
                break;
            case 'CdA':
                aVal = aResults.CdA || 0;
                bVal = bResults.CdA || 0;
                break;
            case 'Fd':
                aVal = aForces.drag_N || 0;
                bVal = bForces.drag_N || 0;
                break;
            case 'Fl':
                aVal = aForces.lift_N || 0;
                bVal = bForces.lift_N || 0;
                break;
            default:
                aVal = aCoef.Cd || 0;
                bVal = bCoef.Cd || 0;
        }

        if (aVal < bVal) return compareSortDirection === 'asc' ? -1 : 1;
        if (aVal > bVal) return compareSortDirection === 'asc' ? 1 : -1;
        return 0;
    });

    // Find best (lowest) values for highlighting
    const allCd = selectedJobData.map(j => j.results?.coefficients?.Cd || 999);
    const allCdA = selectedJobData.map(j => j.results?.CdA || 999);
    const allFd = selectedJobData.map(j => j.results?.forces?.drag_N || 999);
    const bestCd = Math.min(...allCd);
    const bestCdA = Math.min(...allCdA);
    const bestFd = Math.min(...allFd);

    container.innerHTML = `
        <table class="compare-table">
            <thead>
                <tr>
                    <th onclick="sortCompare('name')" class="${compareSortField === 'name' ? 'sorted' : ''}">
                        Simulation ${compareSortField === 'name' ? (compareSortDirection === 'asc' ? '↑' : '↓') : ''}
                    </th>
                    <th>Quality</th>
                    <th>Yaw</th>
                    <th onclick="sortCompare('Cd')" class="${compareSortField === 'Cd' ? 'sorted' : ''}">
                        Cd ${compareSortField === 'Cd' ? (compareSortDirection === 'asc' ? '↑' : '↓') : ''}
                    </th>
                    <th onclick="sortCompare('Cl')" class="${compareSortField === 'Cl' ? 'sorted' : ''}">
                        Cl ${compareSortField === 'Cl' ? (compareSortDirection === 'asc' ? '↑' : '↓') : ''}
                    </th>
                    <th onclick="sortCompare('CdA')" class="${compareSortField === 'CdA' ? 'sorted' : ''}">
                        CdA ${compareSortField === 'CdA' ? (compareSortDirection === 'asc' ? '↑' : '↓') : ''}
                    </th>
                    <th onclick="sortCompare('Fd')" class="${compareSortField === 'Fd' ? 'sorted' : ''}">
                        Fd ${compareSortField === 'Fd' ? (compareSortDirection === 'asc' ? '↑' : '↓') : ''}
                    </th>
                    <th onclick="sortCompare('Fl')" class="${compareSortField === 'Fl' ? 'sorted' : ''}">
                        Fl ${compareSortField === 'Fl' ? (compareSortDirection === 'asc' ? '↑' : '↓') : ''}
                    </th>
                    <th></th>
                </tr>
            </thead>
            <tbody>
                ${selectedJobData.map(job => {
                    const config = job.config || {};
                    const results = job.results || {};
                    const coef = results.coefficients || {};
                    const forces = results.forces || {};
                    const yaw = config.yaw_angles?.[0] || 0;

                    const Cd = coef.Cd || 0;
                    const Cl = coef.Cl || 0;
                    const CdA = (results.CdA || 0) * 10000;
                    const Fd = forces.drag_N || 0;
                    const Fl = forces.lift_N || 0;

                    return `
                        <tr>
                            <td>
                                <strong>${job.name}</strong>
                                <span class="compare-speed">${config.speed} m/s</span>
                            </td>
                            <td><span class="quality-badge ${config.quality}">${config.quality?.toUpperCase()}</span></td>
                            <td>${yaw}°</td>
                            <td class="${Cd === bestCd ? 'best-value' : ''}">${Cd.toFixed(4)}</td>
                            <td>${Cl.toFixed(4)}</td>
                            <td class="${(results.CdA || 0) === bestCdA ? 'best-value' : ''}">${CdA.toFixed(2)} cm²</td>
                            <td class="${Fd === bestFd ? 'best-value' : ''}">${Fd.toFixed(3)} N</td>
                            <td>${Fl.toFixed(3)} N</td>
                            <td>
                                <button class="btn-icon" onclick="showJobResults('${job.id}')" title="View details">
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <circle cx="12" cy="12" r="10"/>
                                        <line x1="12" y1="16" x2="12" y2="12"/>
                                        <line x1="12" y1="8" x2="12.01" y2="8"/>
                                    </svg>
                                </button>
                            </td>
                        </tr>
                    `;
                }).join('')}
            </tbody>
        </table>

        <div class="compare-summary">
            <p><strong>${selectedJobData.length}</strong> simulations compared</p>
            <p>Best Cd: <strong class="best-value">${bestCd.toFixed(4)}</strong></p>
            <p>Best CdA: <strong class="best-value">${(bestCdA * 10000).toFixed(2)} cm²</strong></p>
        </div>
    `;
}

/**
 * Sort comparison table
 */
function sortCompare(field) {
    if (compareSortField === field) {
        compareSortDirection = compareSortDirection === 'asc' ? 'desc' : 'asc';
    } else {
        compareSortField = field;
        compareSortDirection = 'asc';
    }
    updateComparisonTable();
}

// Make compare functions globally available
window.loadCompareJobs = loadCompareJobs;
window.filterCompareJobs = filterCompareJobs;
window.clearCompareFilters = clearCompareFilters;
window.toggleCompareJob = toggleCompareJob;
window.clearComparison = clearComparison;
window.sortCompare = sortCompare;

// =============================================================================
// Project Organization (Phase 4 - US-006)
// =============================================================================

// State for projects
let projects = [];
let currentProjectId = null;

/**
 * Load projects from localStorage (or API in future)
 */
function loadProjects() {
    const stored = localStorage.getItem('wheelflow_projects');
    if (stored) {
        projects = JSON.parse(stored);
    }
    renderProjects();
}

/**
 * Save projects to localStorage
 */
function saveProjectsToStorage() {
    localStorage.setItem('wheelflow_projects', JSON.stringify(projects));
}

/**
 * Render the projects list
 */
async function renderProjects() {
    const container = document.getElementById('projects-content');
    const emptyState = document.getElementById('projects-empty');

    // If viewing a specific project, show its simulations
    if (currentProjectId) {
        renderProjectDetail(currentProjectId);
        return;
    }

    if (projects.length === 0) {
        if (emptyState) emptyState.style.display = 'block';
        return;
    }

    if (emptyState) emptyState.style.display = 'none';

    // Fetch all jobs to count per project
    let allJobs = [];
    try {
        const response = await fetch('/api/jobs');
        if (response.ok) {
            allJobs = await response.json();
        }
    } catch (e) {
        console.error('Failed to fetch jobs:', e);
    }

    container.innerHTML = `
        <div class="projects-grid">
            ${projects.map(project => {
                const jobCount = allJobs.filter(j =>
                    project.jobIds && project.jobIds.includes(j.id)
                ).length;

                return `
                    <div class="project-card" onclick="openProject('${project.id}')">
                        <div class="project-card-header">
                            <svg class="project-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                            </svg>
                            <div class="project-card-actions">
                                <button class="btn-icon" onclick="event.stopPropagation(); editProject('${project.id}')" title="Edit">
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                                    </svg>
                                </button>
                                <button class="btn-icon" onclick="event.stopPropagation(); deleteProject('${project.id}')" title="Delete">
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <polyline points="3 6 5 6 21 6"/>
                                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                                    </svg>
                                </button>
                            </div>
                        </div>
                        <h3 class="project-card-title">${project.name}</h3>
                        ${project.description ? `<p class="project-card-desc">${project.description}</p>` : ''}
                        <div class="project-card-meta">
                            <span>${jobCount} simulation${jobCount !== 1 ? 's' : ''}</span>
                            <span>Created ${formatDate(project.createdAt)}</span>
                        </div>
                    </div>
                `;
            }).join('')}
        </div>
    `;
}

/**
 * Render detail view for a specific project
 */
async function renderProjectDetail(projectId) {
    const container = document.getElementById('projects-content');
    const breadcrumb = document.getElementById('projects-breadcrumb');
    const project = projects.find(p => p.id === projectId);

    if (!project) {
        showToast('Project not found', 'error');
        currentProjectId = null;
        renderProjects();
        return;
    }

    // Update breadcrumb
    if (breadcrumb) {
        breadcrumb.innerHTML = `
            <span class="breadcrumb-item" onclick="closeProjectDetail()">All Projects</span>
            <svg class="breadcrumb-sep" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="9 18 15 12 9 6"/>
            </svg>
            <span class="breadcrumb-item active">${project.name}</span>
        `;
    }

    // Fetch jobs for this project
    let projectJobs = [];
    try {
        const response = await fetch('/api/jobs');
        if (response.ok) {
            const allJobs = await response.json();
            projectJobs = allJobs.filter(j =>
                project.jobIds && project.jobIds.includes(j.id)
            );
        }
    } catch (e) {
        console.error('Failed to fetch jobs:', e);
    }

    container.innerHTML = `
        <div class="project-detail">
            <div class="project-detail-header">
                <div>
                    <h2>${project.name}</h2>
                    ${project.description ? `<p class="project-description">${project.description}</p>` : ''}
                </div>
                <div class="project-detail-actions">
                    <button class="btn-secondary" onclick="showAssignModal('${projectId}')">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="12" y1="5" x2="12" y2="19"/>
                            <line x1="5" y1="12" x2="19" y2="12"/>
                        </svg>
                        Add Simulations
                    </button>
                </div>
            </div>

            ${projectJobs.length === 0 ? `
                <div class="empty-state">
                    <svg class="empty-state-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <circle cx="12" cy="12" r="10"/>
                        <polyline points="12 6 12 12 16 14"/>
                    </svg>
                    <h3>No simulations in this project</h3>
                    <p>Add simulations to organize them together.</p>
                    <button class="btn-cta" onclick="showAssignModal('${projectId}')">
                        Add Simulations
                    </button>
                </div>
            ` : `
                <table class="jobs-table">
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Quality</th>
                            <th>Status</th>
                            <th>Yaw Angles</th>
                            <th>Created</th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody>
                        ${projectJobs.map(job => renderProjectJobRow(job, projectId)).join('')}
                    </tbody>
                </table>
            `}
        </div>
    `;
}

/**
 * Render a job row in project detail
 */
function renderProjectJobRow(job, projectId) {
    const config = job.config || {};
    const quality = config.quality || 'standard';
    const yawAngles = config.yaw_angles || [];

    return `
        <tr onclick="showJobResults('${job.id}')">
            <td>
                <strong>${job.name}</strong>
                <span style="font-size: 0.75rem; color: var(--text-secondary); display: block;">
                    ${config.speed ? config.speed + ' m/s' : ''}
                </span>
            </td>
            <td><span class="quality-badge ${quality}">${quality.toUpperCase()}</span></td>
            <td><span class="status-dot ${job.status}">${formatStatus(job.status)}</span></td>
            <td>
                <div class="yaw-angles-list">
                    ${yawAngles.slice(0, 3).map(yaw => `<span class="yaw-chip">${yaw}°</span>`).join('')}
                    ${yawAngles.length > 3 ? `<span class="yaw-chip">+${yawAngles.length - 3}</span>` : ''}
                </div>
            </td>
            <td>${formatDate(job.created_at)}</td>
            <td>
                <button class="btn-icon" onclick="event.stopPropagation(); removeFromProject('${job.id}', '${projectId}')" title="Remove from project">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"/>
                        <line x1="6" y1="6" x2="18" y2="18"/>
                    </svg>
                </button>
            </td>
        </tr>
    `;
}

/**
 * Open a project to view its contents
 */
function openProject(projectId) {
    currentProjectId = projectId;
    renderProjects();
}

/**
 * Close project detail view and go back to list
 */
function closeProjectDetail() {
    currentProjectId = null;

    // Reset breadcrumb
    const breadcrumb = document.getElementById('projects-breadcrumb');
    if (breadcrumb) {
        breadcrumb.innerHTML = '<span class="breadcrumb-item active">All Projects</span>';
    }

    renderProjects();
}

/**
 * Show the create project modal
 */
function showCreateProjectModal() {
    document.getElementById('project-modal-title').textContent = 'New Project';
    document.getElementById('project-id').value = '';
    document.getElementById('project-name').value = '';
    document.getElementById('project-description').value = '';
    document.getElementById('project-modal').classList.remove('hidden');
}

/**
 * Edit an existing project
 */
function editProject(projectId) {
    const project = projects.find(p => p.id === projectId);
    if (!project) return;

    document.getElementById('project-modal-title').textContent = 'Edit Project';
    document.getElementById('project-id').value = projectId;
    document.getElementById('project-name').value = project.name;
    document.getElementById('project-description').value = project.description || '';
    document.getElementById('project-modal').classList.remove('hidden');
}

/**
 * Close the project modal
 */
function closeProjectModal() {
    document.getElementById('project-modal').classList.add('hidden');
}

/**
 * Save a project (create or update)
 */
function saveProject(event) {
    event.preventDefault();

    const id = document.getElementById('project-id').value;
    const name = document.getElementById('project-name').value.trim();
    const description = document.getElementById('project-description').value.trim();

    if (!name) {
        showToast('Project name is required', 'error');
        return;
    }

    if (id) {
        // Update existing
        const project = projects.find(p => p.id === id);
        if (project) {
            project.name = name;
            project.description = description;
            project.updatedAt = new Date().toISOString();
        }
    } else {
        // Create new
        const newProject = {
            id: 'proj_' + Date.now(),
            name: name,
            description: description,
            jobIds: [],
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString()
        };
        projects.push(newProject);
    }

    saveProjectsToStorage();
    closeProjectModal();
    renderProjects();
    showToast(id ? 'Project updated' : 'Project created', 'success');
}

/**
 * Delete a project
 */
function deleteProject(projectId) {
    const project = projects.find(p => p.id === projectId);
    if (!project) return;

    if (!confirm(`Delete project "${project.name}"? Simulations will not be deleted.`)) {
        return;
    }

    projects = projects.filter(p => p.id !== projectId);
    saveProjectsToStorage();

    if (currentProjectId === projectId) {
        closeProjectDetail();
    } else {
        renderProjects();
    }

    showToast('Project deleted', 'success');
}

/**
 * Show the assign simulations modal
 */
async function showAssignModal(projectId) {
    const modal = document.getElementById('assign-modal');
    const list = document.getElementById('assign-project-list');

    // Store current project ID
    modal.dataset.projectId = projectId;

    // Fetch all jobs
    let allJobs = [];
    try {
        const response = await fetch('/api/jobs');
        if (response.ok) {
            allJobs = await response.json();
        }
    } catch (e) {
        console.error('Failed to fetch jobs:', e);
    }

    const project = projects.find(p => p.id === projectId);
    const assignedIds = project?.jobIds || [];

    // Filter to only completed jobs
    const availableJobs = allJobs.filter(j => j.status === 'complete');

    if (availableJobs.length === 0) {
        list.innerHTML = `
            <div class="empty-state" style="padding: 1rem;">
                <p>No completed simulations available.</p>
            </div>
        `;
    } else {
        list.innerHTML = availableJobs.map(job => {
            const isAssigned = assignedIds.includes(job.id);
            return `
                <div class="assign-job-item ${isAssigned ? 'assigned' : ''}" onclick="toggleJobAssignment('${job.id}')">
                    <input type="checkbox" ${isAssigned ? 'checked' : ''} onclick="event.stopPropagation(); toggleJobAssignment('${job.id}')">
                    <div class="assign-job-info">
                        <strong>${job.name}</strong>
                        <span>${job.config?.speed} m/s | ${job.config?.yaw_angles?.join('°, ')}°</span>
                    </div>
                </div>
            `;
        }).join('');
    }

    modal.classList.remove('hidden');
}

/**
 * Close the assign modal
 */
function closeAssignModal() {
    document.getElementById('assign-modal').classList.add('hidden');
}

/**
 * Toggle job assignment to current project
 */
function toggleJobAssignment(jobId) {
    const modal = document.getElementById('assign-modal');
    const projectId = modal.dataset.projectId;
    const project = projects.find(p => p.id === projectId);

    if (!project) return;

    if (!project.jobIds) {
        project.jobIds = [];
    }

    const index = project.jobIds.indexOf(jobId);
    if (index === -1) {
        project.jobIds.push(jobId);
    } else {
        project.jobIds.splice(index, 1);
    }

    saveProjectsToStorage();

    // Refresh the modal
    showAssignModal(projectId);

    // Refresh the project detail if viewing
    if (currentProjectId === projectId) {
        renderProjectDetail(projectId);
    }
}

/**
 * Remove a job from a project
 */
function removeFromProject(jobId, projectId) {
    const project = projects.find(p => p.id === projectId);
    if (!project || !project.jobIds) return;

    project.jobIds = project.jobIds.filter(id => id !== jobId);
    saveProjectsToStorage();
    renderProjectDetail(projectId);
    showToast('Simulation removed from project', 'success');
}

// Make project functions globally available
window.loadProjects = loadProjects;
window.openProject = openProject;
window.closeProjectDetail = closeProjectDetail;
window.showCreateProjectModal = showCreateProjectModal;
window.editProject = editProject;
window.closeProjectModal = closeProjectModal;
window.saveProject = saveProject;
window.deleteProject = deleteProject;
window.showAssignModal = showAssignModal;
window.closeAssignModal = closeAssignModal;
window.toggleJobAssignment = toggleJobAssignment;
window.removeFromProject = removeFromProject;

// =============================================================================
// Global Functions
// =============================================================================

// Make functions globally available for onclick handlers
window.clearUpload = clearUpload;
window.resetCamera = resetCamera;
window.toggleWireframe = toggleWireframe;
window.showJobResults = showJobResults;
window.showView = function(viewName) {
    // Remove active class from all views
    document.querySelectorAll('.view').forEach(v => {
        v.classList.remove('active');
    });

    // Add active class to the target view
    const targetView = document.getElementById(`${viewName}-view`);
    if (targetView) {
        targetView.classList.add('active');
    }

    // Update nav button state
    document.querySelectorAll('.nav-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.view === viewName);
    });

    // Load view-specific data
    if (viewName === 'jobs') {
        refreshJobs();
    } else if (viewName === 'compare') {
        loadCompareJobs();
    } else if (viewName === 'projects') {
        loadProjects();
    }
};
