import type { ApiRequestOptions, ApiError, ApiErrorMessageFields } from '../../../../../ts-types/domain/map-transport.ts';

const parseResponseBody = async (response: Response): Promise<unknown> => {
    const contentType = response.headers?.get?.('content-type') || '';

    if (contentType.includes('application/json')) {
        try {
            return await response.json();
        } catch {
            return null;
        }
    }

    if (typeof response.text === 'function') {
        const text = await response.text();
        if (!text) {
            return null;
        }

        try {
            return JSON.parse(text);
        } catch {
            return text;
        }
    }

    if (typeof response.json === 'function') {
        try {
            return await response.json();
        } catch {
            return null;
        }
    }

    return null;
};

const getErrorMessage = (response: Response, data: unknown): string => {
    if (data && typeof data === 'object') {
        return (data as ApiErrorMessageFields).message || (data as ApiErrorMessageFields).error || (data as ApiErrorMessageFields).detail || response.statusText || 'API request failed';
    }

    if (typeof data === 'string' && data.trim()) {
        return data;
    }

    return response.statusText || 'API request failed';
};

/** Own JSON request policy while resolving the injected CSRF provider at invocation. */
export function createMapTransport(getCSRFToken: () => string) {
    return async <Result>(url: string, method = 'GET', body: unknown = null, isFormData = false, { signal }: ApiRequestOptions = {}): Promise<Result> => {
        const headers: Record<string, string> = {
            'X-CSRFToken': getCSRFToken()
        };

        if (!isFormData) {
            headers['Content-Type'] = 'application/json';
        }

        const config: RequestInit = {
            method,
            headers,
            credentials: 'same-origin',
            ...(signal ? { signal } : {}),
        };

        if (body) {
            config.body = isFormData ? body as FormData : JSON.stringify(body);
        }

        const response = await fetch(url, config);

        // Handle 204 No Content
        if (response.status === 204) {
            return { ok: true, status: 204 } as Result;
        }

        const data = await parseResponseBody(response);

        if (!response.ok) {
            const error = new Error(getErrorMessage(response, data)) as ApiError;
            error.data = data;
            error.status = response.status;
            throw error;
        }

        // Endpoint serializers own the successful wire contract; preserve unchecked legacy responses.
        return data as Result;
    };

}
