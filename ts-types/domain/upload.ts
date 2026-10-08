export interface UploadError extends Error {
    status: number;
    ambiguous?: boolean;
    payload?: unknown;
}
export interface UploadOptions<Result = unknown> {
    onProgress?: (percent: number, loaded: number, total: number) => void;
    onSuccess?: (response: Result | null) => void;
    onError?: (error: UploadError) => void;
    onUploaded?: (this: XMLHttpRequestUpload, event: ProgressEvent<XMLHttpRequestEventTarget>) => void;
    csrfToken?: string;
    method?: string;
}
/** Serializer error keys are dynamic backend field names. */
export interface UploadErrorPayload {
    message?: unknown;
    error?: unknown;
    detail?: unknown;
    errors?: Record<string, unknown> | null;
}
