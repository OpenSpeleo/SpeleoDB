/**
 * Upload Progress Component
 * 
 * Provides a reusable upload functionality with progress tracking
 * for large file uploads (Station Resources, Journal Entries, etc.)
 */

import { Utils } from '../utils.js';

/**
 * Upload a FormData object with progress tracking
 * @param {string} url - The API endpoint URL
 * @param {FormData} formData - The form data to upload
 * @param {Object} options - Configuration options
 * @param {Function} options.onProgress - Callback for progress updates (percent, loaded, total)
 * @param {Function} options.onSuccess - Callback on successful upload (response data)
 * @param {Function} options.onError - Callback on error (error object)
 * @param {string} options.method - HTTP method (default: 'POST')
 * @returns {XMLHttpRequest} - The XHR object (can be used to abort)
 */
export function uploadWithProgress(url, formData, options = {}) {
    const {
        onProgress = () => {},
        onSuccess = () => {},
        onError = () => {},
        method = 'POST'
    } = options;

    const xhr = new XMLHttpRequest();

    xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
            const percent = Math.round((e.loaded / e.total) * 100);
            onProgress(percent, e.loaded, e.total);
        }
    });

    xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
            try {
                const response = JSON.parse(xhr.responseText);
                onSuccess(response);
            } catch {
                onSuccess({ success: true });
            }
        } else {
            let errorMessage = 'Upload failed';
            try {
                const errorData = JSON.parse(xhr.responseText);
                errorMessage = errorData.message || errorData.error || errorData.detail || errorMessage;
            } catch {
                // Use default error message
            }
            onError(new Error(errorMessage));
        }
    });

    xhr.addEventListener('error', () => {
        onError(new Error('Network error during upload'));
    });

    xhr.addEventListener('abort', () => {
        onError(new Error('Upload cancelled'));
    });

    xhr.open(method, url);
    xhr.setRequestHeader('X-CSRFToken', Utils.getCSRFToken());
    xhr.send(formData);

    return xhr;
}

/**
 * Format bytes to human readable string
 * @param {number} bytes - Number of bytes
 * @returns {string} - Formatted string (e.g., "45.2 MB")
 */
function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

/**
 * Create and return upload progress bar HTML
 * @param {string} id - Unique ID for the progress bar
 * @returns {string} - HTML string for the progress bar
 */
export function createProgressBarHTML(id = 'upload-progress') {
    return `
        <div id="${id}-container" class="hidden mt-4">
            <div class="bg-slate-700/50 rounded-lg p-4 border border-slate-600/50">
                <div class="flex items-center justify-between mb-2">
                    <span class="text-sm text-slate-300 flex items-center gap-2">
                        <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        <span id="${id}-status">Uploading...</span>
                    </span>
                    <span id="${id}-percent" class="text-sm font-medium text-white">0%</span>
                </div>
                <div class="w-full bg-slate-600 rounded-full h-2.5 overflow-hidden">
                    <div id="${id}-bar" class="bg-gradient-to-r from-blue-500 to-cyan-400 h-2.5 rounded-full transition-all duration-300 ease-out" style="width: 0%"></div>
                </div>
                <div class="flex items-center justify-between mt-2">
                    <span id="${id}-size" class="text-xs text-slate-400">0 B / 0 B</span>
                    <button id="${id}-cancel" type="button" class="text-xs text-red-400 hover:text-red-300 transition-colors">
                        Cancel Upload
                    </button>
                </div>
            </div>
        </div>
    `;
}

/**
 * Upload Progress Controller
 * Manages the progress bar UI and upload state
 */
export class UploadProgressController {
    constructor(containerId = 'upload-progress') {
        this.containerId = containerId;
        this.xhr = null;
    }

    /**
     * Get DOM elements for the progress bar
     */
    getElements() {
        return {
            container: document.getElementById(`${this.containerId}-container`),
            bar: document.getElementById(`${this.containerId}-bar`),
            percent: document.getElementById(`${this.containerId}-percent`),
            size: document.getElementById(`${this.containerId}-size`),
            status: document.getElementById(`${this.containerId}-status`),
            cancelBtn: document.getElementById(`${this.containerId}-cancel`)
        };
    }

    /**
     * Show the progress bar
     */
    show() {
        const { container, cancelBtn } = this.getElements();
        if (container) {
            container.classList.remove('hidden');
            this.update(0, 0, 0);
        }
        if (cancelBtn) {
            cancelBtn.onclick = () => this.cancel();
        }
    }

    /**
     * Hide the progress bar
     */
    hide() {
        const { container } = this.getElements();
        if (container) {
            container.classList.add('hidden');
        }
    }

    /**
     * Update progress bar
     * @param {number} percent - Upload progress percentage
     * @param {number} loaded - Bytes uploaded
     * @param {number} total - Total bytes
     */
    update(percent, loaded, total) {
        const { bar, percent: percentEl, size, status } = this.getElements();
        
        if (bar) {
            bar.style.width = `${percent}%`;
        }
        if (percentEl) {
            percentEl.textContent = `${percent}%`;
        }
        if (size) {
            size.textContent = `${formatBytes(loaded)} / ${formatBytes(total)}`;
        }
        if (status) {
            if (percent >= 100) {
                status.textContent = 'Processing...';
            } else {
                status.textContent = 'Uploading...';
            }
        }
    }

    /**
     * Mark upload as complete
     */
    complete() {
        const { status, cancelBtn } = this.getElements();
        if (status) {
            status.innerHTML = `
                <svg class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                </svg>
                <span class="text-emerald-400">Upload complete!</span>
            `;
        }
        if (cancelBtn) {
            cancelBtn.classList.add('hidden');
        }
    }

    /**
     * Mark upload as failed
     * @param {string} message - Error message
     */
    error(message) {
        const { status, cancelBtn, bar } = this.getElements();
        if (status) {
            status.innerHTML = `
                <svg class="w-4 h-4 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
                <span class="text-red-400">${message || 'Upload failed'}</span>
            `;
        }
        if (bar) {
            bar.classList.remove('from-blue-500', 'to-cyan-400');
            bar.classList.add('bg-red-500');
        }
        if (cancelBtn) {
            cancelBtn.classList.add('hidden');
        }
    }

    /**
     * Cancel the current upload
     */
    cancel() {
        if (this.xhr) {
            this.xhr.abort();
            this.xhr = null;
        }
        this.hide();
    }

    /**
     * Set the XHR object for potential cancellation
     * @param {XMLHttpRequest} xhr 
     */
    setXHR(xhr) {
        this.xhr = xhr;
    }

    /**
     * Upload with progress - convenience method
     * @param {string} url - Upload URL
     * @param {FormData} formData - Form data
     * @param {string} method - HTTP method
     * @returns {Promise} - Resolves with response data, rejects on error
     */
    upload(url, formData, method = 'POST') {
        return new Promise((resolve, reject) => {
            this.show();

            const xhr = uploadWithProgress(url, formData, {
                method,
                onProgress: (percent, loaded, total) => {
                    this.update(percent, loaded, total);
                },
                onSuccess: (response) => {
                    this.complete();
                    setTimeout(() => this.hide(), 1500);
                    resolve(response);
                },
                onError: (error) => {
                    this.error(error.message);
                    reject(error);
                }
            });

            this.setXHR(xhr);
        });
    }
}
