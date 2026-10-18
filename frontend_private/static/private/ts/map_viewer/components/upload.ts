import type { UploadError, UploadErrorPayload, UploadOptions, UploadOperation } from '../../../../../../ts-types/domain/upload.ts';
/**
 * Upload Progress Component
 *
 * Provides a reusable upload functionality with progress tracking
 * for large file uploads (Station Resources, Journal Entries, etc.)
 */

import { ApiRequestError } from '../../../../../../frontend_common/api/client.ts';

/** Preserve simple API messages and make serializer field errors actionable. */
export function getUploadErrorMessage(data: unknown): string {
    for (const key of ['message', 'error', 'detail'] as const) {
        if (typeof (data as UploadErrorPayload | null | undefined)?.[key] === 'string') return (data as UploadErrorPayload)[key] as string;
    }
    if ((data as UploadErrorPayload | null | undefined)?.errors && typeof (data as UploadErrorPayload).errors === 'object') {
        const messages = Object.entries((data as UploadErrorPayload).errors!).flatMap(([field, values]) => {
            const text = (Array.isArray(values) ? values : [values]).filter(value => typeof value === 'string').join(' ');
            return text ? [`${field.replaceAll('_', ' ')}: ${text}`] : [];
        });
        if (messages.length) return messages.join(' ');
    }
    return 'Upload failed';
}

/** Run a generated operation with real upload progress and an abortable request. */
export function uploadWithProgress<Result>(operation: UploadOperation<Result>, options: UploadOptions<Result> = {}) {
    const controller = new AbortController();
    void Promise.resolve().then(() => operation({
        signal: controller.signal,
        onUploadProgress: event => {
            if (event.lengthComputable && event.total) {
                options.onProgress?.(Math.round(event.loaded / event.total * 100), event.loaded, event.total);
            }
        },
        onUploadComplete: () => options.onUploaded?.(),
    })).then(
        result => options.onSuccess?.(result),
        (error: unknown) => {
            const status = error instanceof ApiRequestError ? error.status : 0;
            const payload = error instanceof ApiRequestError ? error.data : undefined;
            const unreadable = status >= 200 && status < 300;
            const message = controller.signal.aborted ? 'Upload cancelled'
                : unreadable ? 'The server returned an unreadable response. Check whether the upload was saved before retrying.'
                    : error instanceof ApiRequestError ? getUploadErrorMessage(payload)
                        : 'Network error during upload';
            const failure = new Error(message, { cause: error });
            if (controller.signal.aborted) failure.name = 'AbortError';
            options.onError?.(Object.assign(failure, {
                status,
                ambiguous: !controller.signal.aborted && (status === 0 || status >= 500 || unreadable),
                payload,
            }));
        },
    );
    return controller;
}

/**
 * Format bytes to human readable string
 * @param {number} bytes - Number of bytes
 * @returns {string} - Formatted string (e.g., "45.2 MB")
 */
function formatBytes(bytes: number) {
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
            <div class="bg-srgb-slate-700-50 rounded-lg p-4 border border-srgb-slate-600-50">
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
                    <div id="${id}-bar" class="bg-linear-to-r/srgb from-blue-500 to-cyan-400 h-2.5 rounded-full transition-all duration-300 ease-out" style="width: 0%"></div>
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
    declare containerId: string;
    declare request: AbortController | null;
    constructor(containerId = 'upload-progress') {
        this.containerId = containerId;
        this.request = null;
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
    update(percent: number, loaded: number, total: number) {
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
    error(message?: string) {
        const { status, cancelBtn, bar } = this.getElements();
        if (status) {
            status.textContent = '';
            const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            icon.setAttribute('class', 'w-4 h-4 text-red-400');
            icon.setAttribute('fill', 'none');
            icon.setAttribute('stroke', 'currentColor');
            icon.setAttribute('viewBox', '0 0 24 24');
            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.setAttribute('stroke-linecap', 'round');
            path.setAttribute('stroke-linejoin', 'round');
            path.setAttribute('stroke-width', '2');
            path.setAttribute('d', 'M6 18L18 6M6 6l12 12');
            icon.appendChild(path);
            const msgSpan = document.createElement('span');
            msgSpan.className = 'text-red-400';
            msgSpan.textContent = message || 'Upload failed';
            status.appendChild(icon);
            status.appendChild(msgSpan);
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
        if (this.request) {
            this.request.abort();
            this.request = null;
        }
        this.hide();
    }

    /** Set the current generated request's cancellation controller. */
    setRequest(request: AbortController) {
        this.request = request;
    }

    /** Upload through a generated operation while retaining the progress UI lifecycle. */
    upload<Result>(operation: UploadOperation<Result>): Promise<Result> {
        return new Promise<Result>((resolve, reject) => {
            this.show();
            const request = uploadWithProgress(operation, {
                onProgress: (percent, loaded, total) => this.update(percent, loaded, total),
                onSuccess: response => {
                    this.request = null;
                    this.complete();
                    setTimeout(() => this.hide(), 1500);
                    resolve(response);
                },
                onError: error => {
                    this.request = null;
                    this.error(error.message);
                    reject(error);
                },
            });
            this.setRequest(request);
        });
    }
}
