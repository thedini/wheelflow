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

async function handleFile(file) {
    const validExtensions = ['.stl', '.obj'];
    const ext = file.name.toLowerCase().slice(file.name.lastIndexOf('.'));

    if (!validExtensions.includes(ext)) {
        showToast('Please upload an STL or OBJ file', 'error');
        return;
    }

    uploadedFile = file;

    // Show file info
    const fileInfo = document.getElementById('file-info');
    fileInfo.classList.remove('hidden');
    fileInfo.querySelector('.file-name').textContent = file.name;
    fileInfo.querySelector('.file-size').textContent = formatFileSize(file.size);

    // Upload to server
    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) throw new Error('Upload failed');

        const data = await response.json();
        uploadedFileId = data.id;

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
        showToast('Upload failed: ' + error.message, 'error');
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
    const width = container.clientWidth;
    const height = container.clientHeight || 500;

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

    // Hide placeholder
    const placeholder = container.querySelector('.viewer-placeholder');
    if (placeholder) placeholder.style.display = 'none';

    // Append canvas if not already
    if (!container.querySelector('canvas')) {
        container.appendChild(renderer.domElement);
    }

    // Remove existing mesh
    if (mesh) {
        scene.remove(mesh);
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

        try {
            const response = await fetch('/api/simulate', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) throw new Error('Failed to start simulation');

            const data = await response.json();
            showToast(`Simulation started: ${data.job_id}`, 'success');

            // Switch to jobs view
            document.querySelector('.nav-btn[data-view="jobs"]').click();

        } catch (error) {
            showToast('Error: ' + error.message, 'error');
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

    // Sort by date (newest first)
    jobs.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

    container.innerHTML = jobs.map(job => `
        <div class="job-card" onclick="showJobResults('${job.id}')">
            <div class="job-status ${job.status}"></div>
            <div class="job-info">
                <div class="job-name">${job.name}</div>
                <div class="job-meta">
                    ${job.status} · ${formatDate(job.created_at)}
                    ${job.config ? ` · ${job.config.speed} m/s` : ''}
                </div>
            </div>
            <div class="job-progress">
                <div class="job-progress-bar" style="width: ${job.progress}%"></div>
            </div>
        </div>
    `).join('');
}

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

function renderResults(job) {
    const container = document.getElementById('results-content');

    if (job.status !== 'complete') {
        container.innerHTML = `
            <div class="empty-state">
                <p>Simulation is ${job.status}</p>
                <p>Progress: ${job.progress}%</p>
                ${job.error ? `<p style="color: var(--error)">Error: ${job.error}</p>` : ''}
            </div>
        `;
        return;
    }

    const results = job.results || {};
    const forces = results.forces || {};
    const coefficients = results.coefficients || {};

    container.innerHTML = `
        <div style="margin-bottom: 1.5rem;">
            <h3 style="font-size: 1.25rem; margin-bottom: 0.5rem;">${job.name}</h3>
            <p style="color: var(--text-secondary);">
                Speed: ${job.config.speed} m/s ·
                Yaw: ${job.config.yaw_angles.join('°, ')}° ·
                Quality: ${job.config.quality}
            </p>
        </div>

        <div class="results-grid">
            <div class="result-card">
                <h3>Drag Force</h3>
                <span class="result-value">${(forces.Fd || 0).toFixed(3)}</span>
                <span class="result-unit">N</span>
            </div>

            <div class="result-card">
                <h3>Drag Coefficient</h3>
                <span class="result-value">${(coefficients.Cd || 0).toFixed(4)}</span>
            </div>

            <div class="result-card">
                <h3>CdA</h3>
                <span class="result-value">${((results.CdA || 0) * 1000).toFixed(2)}</span>
                <span class="result-unit">× 10⁻³ m²</span>
            </div>

            <div class="result-card">
                <h3>Lift Force</h3>
                <span class="result-value">${(forces.Fl || 0).toFixed(3)}</span>
                <span class="result-unit">N</span>
            </div>

            <div class="result-card">
                <h3>Side Force</h3>
                <span class="result-value">${(forces.Fs || 0).toFixed(3)}</span>
                <span class="result-unit">N</span>
            </div>

            <div class="result-card">
                <h3>Reynolds Number</h3>
                <span class="result-value">${(job.config.reynolds / 1000).toFixed(1)}k</span>
            </div>
        </div>

        <div style="margin-top: 2rem;">
            <h3 style="margin-bottom: 1rem;">Configuration</h3>
            <pre style="background: var(--bg-tertiary); padding: 1rem; border-radius: var(--radius); overflow-x: auto; font-size: 0.85rem;">
${JSON.stringify(job.config, null, 2)}
            </pre>
        </div>
    `;
}

// Toast
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type}`;

    setTimeout(() => {
        toast.classList.add('hidden');
    }, 3000);
}

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

    if (viewName === 'jobs') {
        refreshJobs();
    }
};
