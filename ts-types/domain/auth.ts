import type { AuthAuthenticationResponse, AuthErrorResponse } from '@speleodb/api';

/** The text fields emitted by the existing allauth templates. */
export interface AuthPayload {
    email?: string;
    name?: string;
    country?: string;
    password?: string;
    password2?: string;
    cave_marker?: string;
    csrfmiddlewaretoken?: string;
    key?: string;
}

/** Error presentation accepts the documented allauth fields and a fallback message. */
export type AuthErrorBody = AuthErrorResponse & Partial<Pick<AuthAuthenticationResponse, 'data'>> & { error?: string };
export interface AuthFailure {
    status?: number;
    data?: AuthErrorBody;
}

export interface AuthFormOptions {
    formId?: string | undefined;
    submit: (payload: AuthPayload) => Promise<unknown>;
    validators?: Array<(payload: AuthPayload, formData: FormData) => string | null | undefined>;
    onSuccess?: () => void;
    successMessage?: string | undefined;
    treat401AsSuccess?: boolean;
    errorHandler?: (xhr: AuthFailure) => string | null | undefined;
    submitBtnId?: string;
    beforeSubmit?: (payload: AuthPayload, formData: FormData) => boolean | void;
}
