/** Wire-level double: test callbacks intentionally receive malformed payloads. */
export interface ControllerAjaxCall {
    url?: string;
    method?: string;
    type?: string;
    data?: unknown;
    headers?: Record<string, string>;
    beforeSend?: (xhr: {setRequestHeader(name: string, value: string): unknown}) => boolean | void;
    success: (data: unknown) => unknown;
    error: (first?: unknown, second?: string) => unknown;
}
