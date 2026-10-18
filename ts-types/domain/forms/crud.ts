/** Form field names vary by caller; hooks may transform their serialized values. */
export type FormPayload = Record<string, unknown>;
export interface EntityCrudOptions<Response = unknown> {
    formId?: string | undefined;
    submit: (payload: FormPayload) => Promise<Response>;
    submitBtnId?: string;
    successMessage?: string | undefined;
    successRedirect?: string | undefined;
    redirectFromResponse?: ((response: Response) => string | null | undefined) | undefined;
    reloadOnSuccess?: boolean | undefined;
    redirectDelayMs?: number;
    beforeSubmit?: ((payload: FormPayload) => boolean | void) | undefined;
    onSuccess?: (response: Response) => void;
    prepare?: ((payload: FormPayload) => FormPayload) | undefined;
    submitOnForm?: boolean;
    onPendingChange?: (pending: boolean) => void;
    showSuccessModal?: boolean;
    onError?: (error: unknown) => void;
}
export interface DangerZoneOptions {
    remove: () => Promise<unknown>;
    successMessage?: string;
    successRedirect?: string;
    redirectDelayMs?: number;
}
export interface MutexLockOptions {
    acquire?: (() => Promise<unknown>) | undefined;
    release?: (() => Promise<unknown>) | undefined;
    lockMessage?: string;
    unlockMessage?: string;
    reloadDelayMs?: number;
}
