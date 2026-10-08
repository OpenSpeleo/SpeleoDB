export interface ApiRequestOptions { signal?: AbortSignal }
export interface ApiNoContent { ok: true; status: 204 }
/** Ordinary Error instances are augmented by apiRequest, without a subclass. */
export interface ApiError extends Error { data: unknown; status: number }
export interface ApiErrorMessageFields { message?: string; error?: string; detail?: string }
