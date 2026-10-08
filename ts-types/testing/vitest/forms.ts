import type { Mock } from 'vitest';
import type { AjaxFailure } from '../../domain/forms/errors.ts';

/** Only callback/transport members consumed by the shared-form unit fixtures. */
export interface FormAjaxCall {
    url: string;
    method: string;
    data?: string;
    beforeSend: (xhr: { setRequestHeader(name: string, value: string): unknown }) => boolean | void;
    success: (response?: unknown) => void;
    error: (xhr: AjaxFailure) => void;
    complete?: () => void;
}
export interface FormTestJQuery {
    (selector: string | Element | Document): JQuery<HTMLElement>;
    ajax: Mock<(options: FormAjaxCall) => unknown>;
}
