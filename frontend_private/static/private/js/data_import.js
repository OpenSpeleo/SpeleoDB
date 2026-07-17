// Data Import Module - Unified interface for GPX and KML/KMZ imports
export const DataImport = (function() {
    let selectedGPXFile = null;
    let selectedKMLFile = null;
    let csrfToken = '';
    let currentTab = 'gpx';
    let landmarkCollectionsLoaded = false;

    // Initialize with CSRF token
    function init(token) {
        csrfToken = token;
        setupEventListeners();
    }

    function setupEventListeners() {
        // GPX file input
        const gpxFileInput = document.getElementById('gpx-file-input');
        const gpxDropZone = document.getElementById('gpx-drop-zone');

        if (gpxFileInput) {
            gpxFileInput.addEventListener('change', function(e) {
                if (e.target.files && e.target.files[0]) {
                    handleGPXFile(e.target.files[0]);
                }
            });
        }

        if (gpxDropZone) {
            gpxDropZone.addEventListener('dragover', function(e) {
                e.preventDefault();
                e.stopPropagation();
                this.classList.add('border-cyan-400', 'bg-srgb-slate-700-50');
            });

            gpxDropZone.addEventListener('dragleave', function(e) {
                e.preventDefault();
                e.stopPropagation();
                this.classList.remove('border-cyan-400', 'bg-srgb-slate-700-50');
            });

            gpxDropZone.addEventListener('drop', function(e) {
                e.preventDefault();
                e.stopPropagation();
                this.classList.remove('border-cyan-400', 'bg-srgb-slate-700-50');

                if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                    handleGPXFile(e.dataTransfer.files[0]);
                }
            });
        }

        // KML file input
        const kmlFileInput = document.getElementById('kml-file-input');
        const kmlDropZone = document.getElementById('kml-drop-zone');

        if (kmlFileInput) {
            kmlFileInput.addEventListener('change', function(e) {
                if (e.target.files && e.target.files[0]) {
                    handleKMLFile(e.target.files[0]);
                }
            });
        }

        if (kmlDropZone) {
            kmlDropZone.addEventListener('dragover', function(e) {
                e.preventDefault();
                e.stopPropagation();
                this.classList.add('border-amber-400', 'bg-srgb-slate-700-50');
            });

            kmlDropZone.addEventListener('dragleave', function(e) {
                e.preventDefault();
                e.stopPropagation();
                this.classList.remove('border-amber-400', 'bg-srgb-slate-700-50');
            });

            kmlDropZone.addEventListener('drop', function(e) {
                e.preventDefault();
                e.stopPropagation();
                this.classList.remove('border-amber-400', 'bg-srgb-slate-700-50');

                if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                    handleKMLFile(e.dataTransfer.files[0]);
                }
            });
        }

        // Close on escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                const importModal = document.getElementById('import-data-modal');
                if (importModal && !importModal.classList.contains('hidden')) {
                    hideModal();
                }
                hideWarningModal();
            }
        });

        // Close when clicking outside modal content
        const importModal = document.getElementById('import-data-modal');
        if (importModal) {
            importModal.addEventListener('click', function(e) {
                if (e.target === this) {
                    hideModal();
                }
            });
        }

        // Setup collapsible instructions toggle
        const instructionsToggle = document.getElementById('kml-instructions-toggle');
        if (instructionsToggle) {
            instructionsToggle.addEventListener('click', function(e) {
                e.preventDefault();
                toggleInstructions();
            });
        }
    }

    function switchTab(tab) {
        currentTab = tab;

        const gpxTab = document.getElementById('import-tab-gpx');
        const kmlTab = document.getElementById('import-tab-kml');
        const gpxContent = document.getElementById('import-content-gpx');
        const kmlContent = document.getElementById('import-content-kml');

        if (tab === 'gpx') {
            gpxTab.classList.add('text-white', 'border-cyan-400', 'bg-srgb-slate-700-50');
            gpxTab.classList.remove('text-slate-400', 'border-transparent');
            kmlTab.classList.remove('text-white', 'border-amber-400', 'bg-srgb-slate-700-50');
            kmlTab.classList.add('text-slate-400', 'border-transparent');
            gpxContent.classList.remove('hidden');
            kmlContent.classList.add('hidden');
        } else {
            kmlTab.classList.add('text-white', 'border-amber-400', 'bg-srgb-slate-700-50');
            kmlTab.classList.remove('text-slate-400', 'border-transparent');
            gpxTab.classList.remove('text-white', 'border-cyan-400', 'bg-srgb-slate-700-50');
            gpxTab.classList.add('text-slate-400', 'border-transparent');
            kmlContent.classList.remove('hidden');
            gpxContent.classList.add('hidden');
        }
    }

    function formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    function handleGPXFile(file) {
        document.getElementById('gpx-error-message').classList.add('hidden');

        // Validate extension
        if (!file.name.toLowerCase().endsWith('.gpx')) {
            showGPXError('Invalid file type. Please select a .gpx file.');
            return;
        }

        selectedGPXFile = file;

        // Show file info
        document.getElementById('gpx-file-name').textContent = file.name;
        document.getElementById('gpx-file-size').textContent = formatFileSize(file.size);
        document.getElementById('gpx-drop-zone').classList.add('hidden');
        document.getElementById('gpx-selected-file').classList.remove('hidden');
        document.getElementById('gpx-upload-btn').disabled = false;
    }

    function handleKMLFile(file) {
        document.getElementById('kml-error-message').classList.add('hidden');

        const fileName = file.name.toLowerCase();
        // Validate extension
        if (!fileName.endsWith('.kml') && !fileName.endsWith('.kmz')) {
            showKMLError('Invalid file type. Please select a .kml or .kmz file.');
            return;
        }

        selectedKMLFile = file;

        // Show file info
        document.getElementById('kml-file-name').textContent = file.name;
        document.getElementById('kml-file-size').textContent = formatFileSize(file.size);
        document.getElementById('kml-drop-zone').classList.add('hidden');
        document.getElementById('kml-selected-file').classList.remove('hidden');
        document.getElementById('kml-upload-btn').disabled = false;
    }

    function showGPXError(message) {
        const errorDiv = document.getElementById('gpx-error-message');
        const errorText = document.getElementById('gpx-error-text');
        errorText.textContent = message;
        errorDiv.classList.remove('hidden');
    }

    function showKMLError(message) {
        const errorDiv = document.getElementById('kml-error-message');
        const errorText = document.getElementById('kml-error-text');
        errorText.textContent = message;
        errorDiv.classList.remove('hidden');
    }

    function showModal() {
        const modal = document.getElementById('import-data-modal');
        if (modal) {
            modal.classList.remove('hidden');
            clearGPXFile();
            clearKMLFile();
            loadLandmarkCollectionSelectors();
            switchTab('gpx');
        }
    }

    async function loadLandmarkCollectionSelectors() {
        if (landmarkCollectionsLoaded) return;

        try {
            const response = await fetch(Urls['api:v2:landmark-collections'](), {
                method: 'GET',
                headers: { 'X-CSRFToken': csrfToken },
                credentials: 'same-origin'
            });
            const collections = await response.json();

            if (!response.ok || !Array.isArray(collections)) {
                return;
            }

            ['gpx-landmark-collection', 'kml-landmark-collection'].forEach(function(selectId) {
                const select = document.getElementById(selectId);
                if (!select) return;

                select.innerHTML = '';
                const writableCollections = collections
                    .filter(function(collection) { return Number(collection.user_permission_level) >= 2; })
                    .sort(function(a, b) {
                        const aPersonal = a.is_personal === true || a.collection_type === 'PERSONAL';
                        const bPersonal = b.is_personal === true || b.collection_type === 'PERSONAL';
                        if (aPersonal !== bPersonal) return aPersonal ? -1 : 1;
                        return String(a.name || '').localeCompare(String(b.name || ''));
                    });

                const hasPersonalCollection = writableCollections.some(function(collection) {
                    return collection.is_personal === true || collection.collection_type === 'PERSONAL';
                });

                if (!hasPersonalCollection) {
                    const personalOption = document.createElement('option');
                    personalOption.value = '';
                    personalOption.textContent = 'Personal Landmarks';
                    select.appendChild(personalOption);
                }

                writableCollections
                    .forEach(function(collection) {
                        const isPersonal = collection.is_personal === true || collection.collection_type === 'PERSONAL';
                        const option = document.createElement('option');
                        option.value = collection.id;
                        option.textContent = isPersonal ? `${collection.name} (Private)` : collection.name;
                        select.appendChild(option);
                    });
            });

            landmarkCollectionsLoaded = true;
        } catch (error) {
            console.error('Failed to load Landmark Collections:', error);
        }
    }

    function hideModal() {
        const modal = document.getElementById('import-data-modal');
        if (modal) {
            modal.classList.add('hidden');
            clearGPXFile();
            clearKMLFile();
        }
    }

    function hideWarningModal() {
        const modal = document.getElementById('import-warning-modal');
        if (modal) {
            modal.classList.add('hidden');
        }
    }

    function clearGPXFile() {
        selectedGPXFile = null;
        const fileInput = document.getElementById('gpx-file-input');
        if (fileInput) fileInput.value = '';

        const dropZone = document.getElementById('gpx-drop-zone');
        const selectedFile = document.getElementById('gpx-selected-file');
        const errorMessage = document.getElementById('gpx-error-message');
        const uploadBtn = document.getElementById('gpx-upload-btn');

        if (dropZone) dropZone.classList.remove('hidden');
        if (selectedFile) selectedFile.classList.add('hidden');
        if (errorMessage) errorMessage.classList.add('hidden');
        if (uploadBtn) uploadBtn.disabled = true;

        // Reset upload button state
        const uploadText = document.getElementById('gpx-upload-text');
        const uploadSpinner = document.getElementById('gpx-upload-spinner');
        if (uploadText) uploadText.textContent = 'Import GPX';
        if (uploadSpinner) uploadSpinner.classList.add('hidden');
    }

    function clearKMLFile() {
        selectedKMLFile = null;
        const fileInput = document.getElementById('kml-file-input');
        if (fileInput) fileInput.value = '';

        const dropZone = document.getElementById('kml-drop-zone');
        const selectedFile = document.getElementById('kml-selected-file');
        const errorMessage = document.getElementById('kml-error-message');
        const uploadBtn = document.getElementById('kml-upload-btn');

        if (dropZone) dropZone.classList.remove('hidden');
        if (selectedFile) selectedFile.classList.add('hidden');
        if (errorMessage) errorMessage.classList.add('hidden');
        if (uploadBtn) uploadBtn.disabled = true;

        // Reset upload button state
        const uploadText = document.getElementById('kml-upload-text');
        const uploadSpinner = document.getElementById('kml-upload-spinner');
        if (uploadText) uploadText.textContent = 'Import KML/KMZ';
        if (uploadSpinner) uploadSpinner.classList.add('hidden');
    }

    async function uploadGPX() {
        if (!selectedGPXFile) return;

        const uploadBtn = document.getElementById('gpx-upload-btn');
        const uploadText = document.getElementById('gpx-upload-text');
        const uploadSpinner = document.getElementById('gpx-upload-spinner');

        // Show loading state
        uploadBtn.disabled = true;
        uploadText.textContent = 'Importing...';
        uploadSpinner.classList.remove('hidden');
        document.getElementById('gpx-error-message').classList.add('hidden');

        try {
            const headers = new Headers();
            headers.append('X-CSRFToken', csrfToken);

            const formData = new FormData();
            formData.append('file', selectedGPXFile, selectedGPXFile.name);
            const collectionId = document.getElementById('gpx-landmark-collection')?.value;
            if (collectionId) {
                formData.append('collection', collectionId);
            }

            const requestOptions = {
                method: 'PUT',
                headers: headers,
                body: formData,
                credentials: 'same-origin',
                redirect: 'follow'
            };

            const response = await fetch(Urls['api:v2:gpx-import'](), requestOptions);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || data.error || data.detail || 'Import failed');
            }

            const landmarksCreated = data?.landmarks_created || 0;
            const tracksCreated = data?.gps_tracks_created || 0;

            if (landmarksCreated > 0 || tracksCreated > 0) {
                // Success - show message and reload
                hideModal();
                showSuccessModal(landmarksCreated, tracksCreated, 'gpx');
            } else {
                // Nothing imported - show warning
                hideModal();
                showWarningModal('gpx');
            }

        } catch (error) {
            console.error('GPX import error:', error);
            showGPXError(error.message || 'Failed to import GPX file');

            // Reset button
            uploadBtn.disabled = false;
            uploadText.textContent = 'Import GPX';
            uploadSpinner.classList.add('hidden');
        }
    }

    async function uploadKML() {
        if (!selectedKMLFile) return;

        const uploadBtn = document.getElementById('kml-upload-btn');
        const uploadText = document.getElementById('kml-upload-text');
        const uploadSpinner = document.getElementById('kml-upload-spinner');

        // Show loading state
        uploadBtn.disabled = true;
        uploadText.textContent = 'Importing...';
        uploadSpinner.classList.remove('hidden');
        document.getElementById('kml-error-message').classList.add('hidden');

        try {
            const headers = new Headers();
            headers.append('X-CSRFToken', csrfToken);

            const formData = new FormData();
            formData.append('file', selectedKMLFile, selectedKMLFile.name);
            const collectionId = document.getElementById('kml-landmark-collection')?.value;
            if (collectionId) {
                formData.append('collection', collectionId);
            }

            const requestOptions = {
                method: 'PUT',
                headers: headers,
                body: formData,
                credentials: 'same-origin',
                redirect: 'follow'
            };

            const response = await fetch(Urls['api:v2:kml-kmz-import'](), requestOptions);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || data.error || data.detail || 'Import failed');
            }

            const landmarksCreated = data?.landmarks_created || 0;

            if (landmarksCreated > 0) {
                // Success - show message and reload landmarks
                hideModal();
                showSuccessModal(landmarksCreated, 0, 'kml');
            } else {
                // Nothing imported - show warning
                hideModal();
                showWarningModal('kml');
            }

        } catch (error) {
            console.error('KML/KMZ import error:', error);
            showKMLError(error.message || 'Failed to import KML/KMZ file');

            // Reset button
            uploadBtn.disabled = false;
            uploadText.textContent = 'Import KML/KMZ';
            uploadSpinner.classList.add('hidden');
        }
    }

    function showSuccessModal(landmarks, tracks, type) {
        const parts = [];
        if (tracks > 0) parts.push(`${tracks} GPS track${tracks > 1 ? 's' : ''}`);
        if (landmarks > 0) parts.push(`${landmarks} landmark${landmarks > 1 ? 's' : ''}`);

        const message = `Successfully imported ${parts.join(' and ')}!`;

        const messageEl = document.getElementById('import-success-message');
        const modal = document.getElementById('import-success-modal');
        const reloadText = document.getElementById('import-success-reload-text');

        if (messageEl) messageEl.textContent = message;
        if (reloadText) reloadText.textContent = 'Refreshing map data...';
        if (modal) modal.classList.remove('hidden');

        // Dispatch events to refresh data without full page reload
        // Refresh landmarks if any were imported
        if (landmarks > 0) {
            window.dispatchEvent(new CustomEvent('speleo:refresh-landmarks'));
        }

        // Refresh GPS tracks if any were imported (only for GPX)
        if (tracks > 0) {
            window.dispatchEvent(new CustomEvent('speleo:refresh-gps-tracks', {
                detail: { deactivateAll: true }
            }));
        }

        // Close success modal after a short delay
        setTimeout(() => {
            if (modal) modal.classList.add('hidden');
        }, 2500);
    }

    function showWarningModal(type) {
        const modal = document.getElementById('import-warning-modal');
        const messageEl = document.getElementById('import-warning-message');

        if (type === 'kml') {
            if (messageEl) messageEl.textContent = "This KML/KMZ file does not contain any new landmarks that aren't already in the system.";
        } else {
            if (messageEl) messageEl.textContent = "This GPX file does not contain any new landmarks or GPS tracks that aren't already in the system.";
        }

        if (modal) modal.classList.remove('hidden');
    }

    function toggleInstructions() {
        const panel = document.getElementById('kml-instructions-panel');
        if (panel) {
            panel.classList.toggle('is-open');
        }
    }

    // Public API
    return {
        init: init,
        showModal: showModal,
        hideModal: hideModal,
        hideWarningModal: hideWarningModal,
        clearGPXFile: clearGPXFile,
        clearKMLFile: clearKMLFile,
        uploadGPX: uploadGPX,
        uploadKML: uploadKML,
        switchTab: switchTab,
        toggleInstructions: toggleInstructions
    };
})();
