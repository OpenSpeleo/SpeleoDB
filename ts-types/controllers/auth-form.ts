export interface AuthFormContext {
    mode: 'login' | 'signup' | 'password-reset' | 'password-reset-from-key';
    formId?: string;
    endpoint?: string;
    successMessage?: string;
    successRedirect?: string;
}
