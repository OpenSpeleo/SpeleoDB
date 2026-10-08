/** The text fields emitted by the existing allauth templates. */
export interface AuthPayload {
    email?: string;
    name?: string;
    password?: string;
    password2?: string;
    cave_marker?: string;
    csrfmiddlewaretoken?: string;
}

export interface AuthErrorBody {
    error?: string;
    errors?: Array<{ message?: string }>;
    data?: { flows?: Array<{ id: string }> };
}

export interface AuthFailure {
    status?: number;
    responseJSON?: AuthErrorBody;
}

export interface AuthFormOptions {
    formId?: string | undefined;
    endpoint?: string | undefined;
    validators?: Array<(payload: AuthPayload, formData: FormData) => string | null | undefined>;
    onSuccess?: () => void;
    successMessage?: string | undefined;
    treat401AsSuccess?: boolean;
    errorHandler?: (xhr: AuthFailure) => string | null | undefined;
    submitBtnId?: string;
    beforeAjax?: (payload: AuthPayload, formData: FormData) => boolean | void;
}
