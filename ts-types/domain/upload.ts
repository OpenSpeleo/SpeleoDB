import type { ApiRequestOptions } from '@speleodb/api';

export type UploadOperation<Result> = (options: Omit<ApiRequestOptions, 'client'>) => Promise<Result>;

export interface UploadError extends Error {
    status: number;
    ambiguous?: boolean;
    payload?: unknown;
}
export interface UploadOptions<Result = unknown> {
    onProgress?: (percent: number, loaded: number, total: number) => void;
    onSuccess?: (response: Result) => void;
    onError?: (error: UploadError) => void;
    onUploaded?: () => void;
}
/** Serializer error keys are dynamic backend field names. */
export interface UploadErrorPayload {
    message?: unknown;
    error?: unknown;
    detail?: unknown;
    errors?: Record<string, unknown> | null;
}
