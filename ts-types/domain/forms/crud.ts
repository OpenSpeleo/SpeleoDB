import type { AjaxFailure } from './errors.ts';

/** Form field names vary by caller; hooks may transform their serialized values. */
export type FormPayload = Record<string, unknown>;
export interface EntityCrudOptions<Response = unknown> {
    formId?: string | undefined;
    endpoint?: string | undefined;
    method?: string | undefined;
    submitBtnId?: string;
    successMessage?: string | undefined;
    successRedirect?: string | undefined;
    redirectFromResponse?: ((response: Response) => string | null | undefined) | undefined;
    reloadOnSuccess?: boolean | undefined;
    redirectDelayMs?: number;
    beforeSubmit?: ((payload: FormPayload) => boolean | void) | undefined;
    onSuccess?: (response: Response) => void;
    serialize?: ((payload: FormPayload) => string) | undefined;
    submitOnForm?: boolean;
    onPendingChange?: (pending: boolean) => void;
    showSuccessModal?: boolean;
    onError?: (xhr: AjaxFailure) => void;
}
export interface DangerZoneOptions {
    deleteUrl?: string;
    successMessage?: string;
    successRedirect?: string;
    redirectDelayMs?: number;
}
export interface MutexLockOptions {
    lockUrl?: string;
    unlockUrl?: string;
    lockMessage?: string;
    unlockMessage?: string;
    reloadDelayMs?: number;
}
