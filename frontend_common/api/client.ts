import { createApiClient } from '@speleodb/api';
import type { ApiClient, ApiRequestOptions } from '@speleodb/api';

let client: ApiClient | undefined;

/** Resolve session/CSRF state at request time, including after an auth transition. */
function sessionHeaders(): HeadersInit {
    const input = document.querySelector<HTMLInputElement>('input[name^="csrfmiddlewaretoken"]');
    const cookie = document.cookie.split('; ').find(value => value.startsWith('csrftoken='))?.slice('csrftoken='.length);
    let token = input?.value || '';
    if (!token && cookie) {
        try { token = decodeURIComponent(cookie); }
        catch { token = cookie; }
    }
    return token ? { 'X-CSRFToken': token } : {};
}

/** Browser policy only; operation URLs and serialization belong to the generated SDK. */
export function webApiOptions(options: Omit<ApiRequestOptions, 'client'> = {}): ApiRequestOptions {
    const origin = window.location.origin;
    if (!client || new URL(client.baseUrl).origin !== origin) client = createApiClient({
        baseUrl: origin,
        credentials: 'same-origin',
        headers: sessionHeaders,
        // Preserve browser upload/conversion flows without a total request deadline.
        // Individual polling flows still supply their own finite budgets.
        timeoutMs: null,
    });
    return { ...options, client };
}

type SuccessStatus = 200 | 201 | 202 | 203 | 204 | 205 | 206 | 207 | 208 | 226;
interface OperationResponse { kind: 'documented' | 'unexpected'; status: number; data: unknown; headers: Headers }
export type SuccessData<Response> = Response extends { kind: 'documented'; status: SuccessStatus; data: infer Data } ? Data : never;

/** Keep server status and validation fields available to each UI's presentation policy. */
export class ApiRequestError extends Error {
    readonly status: number;
    readonly data: unknown;
    readonly headers: Headers;

    constructor(response: OperationResponse) {
        const body = response.data;
        const fields = body && typeof body === 'object' ? body as Record<string, unknown> : {};
        const message = [fields.message, fields.error, fields.detail, typeof body === 'string' ? body : null]
            .find(value => typeof value === 'string' && value.trim());
        super(typeof message === 'string' ? message : `API request failed (${response.status}).`);
        this.name = 'ApiRequestError';
        this.status = response.status;
        this.data = body;
        this.headers = response.headers;
    }
}

/** Unwrap only a documented successful wire response; special statuses stay with their caller. */
export async function apiData<Response extends OperationResponse>(request: Promise<Response>): Promise<SuccessData<Response>> {
    const response = await request;
    if (response.kind !== 'documented' || response.status < 200 || response.status >= 300) {
        throw new ApiRequestError(response);
    }
    return response.data as SuccessData<Response>;
}
