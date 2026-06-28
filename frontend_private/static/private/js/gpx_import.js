// GPX Import Module - Shared between pages
export const GPXImport = (function() {
    let selectedFile = null;
    let csrfToken = '';
    
    // Initialize with CSRF token
    function init(token) {
        csrfToken = token;
        setupEventListeners();
    }
    
    function setupEventListeners() {
        const fileInput = document.getElementById('gpx-file-input');
        const dropZone = document.getElementById('gpx-drop-zone');
        
        if (fileInput) {
            fileInput.addEventListener('change', function(e) {
                if (e.target.files && e.target.files[0]) {
                    handleFile(e.target.files[0]);
                }
            });
        }
        
        if (dropZone) {
            dropZone.addEventListener('dragover', function(e) {
                e.preventDefault();
                e.stopPropagation();
                this.classList.add('border-cyan-400', 'bg-srgb-slate-700-50');
            });
            
            dropZone.addEventListener('dragleave', function(e) {
                e.preventDefault();
                e.stopPropagation();
                this.classList.remove('border-cyan-400', 'bg-srgb-slate-700-50');
            });
            
            dropZone.addEventListener('drop', function(e) {
                e.preventDefault();
                e.stopPropagation();
                this.classList.remove('border-cyan-400', 'bg-srgb-slate-700-50');
                
                if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                    handleFile(e.dataTransfer.files[0]);
                }
            });
        }
        
        // Close on escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                const importModal = document.getElementById('import-gpx-modal');
                if (importModal && !importModal.classList.contains('hidden')) {
                    hideModal();
                }
                hideWarningModal();
            }
        });
        
        // Close when clicking outside modal content
        const importModal = document.getElementById('import-gpx-modal');
        if (importModal) {
            importModal.addEventListener('click', function(e) {
                if (e.target === this) {
                    hideModal();
                }
            });
        }
    }
    
    function formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }
    
    function handleFile(file) {
        document.getElementById('gpx-error-message').classList.add('hidden');
        
        // Validate extension
        if (!file.name.toLowerCase().endsWith('.gpx')) {
            showError('Invalid file type. Please select a .gpx file.');
            return;
        }
        
        selectedFile = file;
        
        // Show file info
        document.getElementById('gpx-file-name').textContent = file.name;
        document.getElementById('gpx-file-size').textContent = formatFileSize(file.size);
        document.getElementById('gpx-drop-zone').classList.add('hidden');
        document.getElementById('gpx-selected-file').classList.remove('hidden');
        document.getElementById('gpx-upload-btn').disabled = false;
    }
    
    function showError(message) {
        const errorDiv = document.getElementById('gpx-error-message');
        const errorText = document.getElementById('gpx-error-text');
        errorText.textContent = message;
        errorDiv.classList.remove('hidden');
    }
    
    function showModal() {
        const modal = document.getElementById('import-gpx-modal');
        if (modal) {
            modal.classList.remove('hidden');
            clearFile();
        }
    }
    
    function hideModal() {
        const modal = document.getElementById('import-gpx-modal');
        if (modal) {
            modal.classList.add('hidden');
            clearFile();
        }
    }
    
    function hideWarningModal() {
        const modal = document.getElementById('gpx-warning-modal');
        if (modal) {
            modal.classList.add('hidden');
        }
    }
    
    function clearFile() {
        selectedFile = null;
        const fileInput = document.getElementById('gpx-file-input');
        if (fileInput) fileInput.value = '';
        
        document.getElementById('gpx-drop-zone').classList.remove('hidden');
        document.getElementById('gpx-selected-file').classList.add('hidden');
        document.getElementById('gpx-error-message').classList.add('hidden');
        document.getElementById('gpx-upload-btn').disabled = true;
        
        // Reset upload button state
        document.getElementById('gpx-upload-text').textContent = 'Import GPX';
        document.getElementById('gpx-upload-spinner').classList.add('hidden');
    }
    
    async function upload() {
        if (!selectedFile) return;
        
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
            formData.append('file', selectedFile, selectedFile.name);
            
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
                showSuccessModal(landmarksCreated, tracksCreated);
            } else {
                // Nothing imported - show warning
                hideModal();
                showWarningModal();
            }
            
        } catch (error) {
            console.error('GPX import error:', error);
            showError(error.message || 'Failed to import GPX file');
            
            // Reset button
            uploadBtn.disabled = false;
            uploadText.textContent = 'Import GPX';
            uploadSpinner.classList.add('hidden');
        }
    }
    
    function showSuccessModal(landmarks, tracks) {
        const parts = [];
        if (tracks > 0) parts.push(`${tracks} GPS track${tracks > 1 ? 's' : ''}`);
        if (landmarks > 0) parts.push(`${landmarks} landmark${landmarks > 1 ? 's' : ''}`);
        
        const message = `Successfully imported ${parts.join(' and ')}!`;
        
        const messageEl = document.getElementById('gpx-success-message');
        const modal = document.getElementById('gpx-success-modal');
        const reloadText = document.getElementById('gpx-success-reload-text');
        
        if (messageEl) messageEl.textContent = message;
        if (reloadText) reloadText.textContent = 'Refreshing map data...';
        if (modal) modal.classList.remove('hidden');
        
        // Dispatch events to refresh data without full page reload
        // Refresh landmarks if any were imported
        if (landmarks > 0) {
            window.dispatchEvent(new CustomEvent('speleo:refresh-landmarks'));
        }
        
        // Refresh GPS tracks if any were imported
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
    
    function showWarningModal() {
        const modal = document.getElementById('gpx-warning-modal');
        if (modal) modal.classList.remove('hidden');
    }
    
    // Public API
    return {
        init: init,
        showModal: showModal,
        hideModal: hideModal,
        hideWarningModal: hideWarningModal,
        clearFile: clearFile,
        upload: upload
    };
})();
