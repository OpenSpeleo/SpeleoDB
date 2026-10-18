export interface AuthFormContext {
    mode: 'login' | 'signup' | 'password-reset' | 'password-reset-from-key';
    formId?: string;
    successMessage?: string;
    successRedirect?: string;
}
