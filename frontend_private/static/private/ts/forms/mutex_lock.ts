import { hideFormStatus, scheduleFormReload } from './lifecycle.ts';
import type { MutexLockOptions } from '../../../../../ts-types/domain/forms/crud.ts';

/**
 * Shared helpers for the project lock / unlock buttons on
 * the project banner and `project/mutex_history.html`.
 *
 * Usage:
 *   attachMutexLock({
 *       acquire: acquireProject,
 *       release: releaseProject,
 *   });
 *
 * - `.btn_unlock` click -> release operation, reload on success
 * - `#btn_lock_project` click -> acquire operation, reload on success
 *
 * Either callback can be omitted if the template does not render the
 * corresponding button.
 *
 * Requires: jQuery, FormModals, showApiErrorModal.
 */

import { showApiErrorModal } from './api_errors.ts';
import { FormModals } from './modals.ts';

function _postMutexAction(action: () => Promise<unknown>, successMessage: string, reloadDelayMs: number, button: HTMLButtonElement) {
    if (button.disabled) return;
    button.disabled = true;
    hideFormStatus();

    void action().then(function () {
            if (reloadDelayMs === 0) {
                window.location.reload();
                return;
            }
            FormModals.showSuccess(successMessage);
            scheduleFormReload(reloadDelayMs);
        }, function (xhr: unknown) {
            button.disabled = false;
            showApiErrorModal(xhr);
        });
}

export function attachMutexLock(options: MutexLockOptions) {
    var acquire = options.acquire;
    var release = options.release;
    var lockMessage = options.lockMessage || 'The project has been locked for edition.';
    var unlockMessage = options.unlockMessage || 'The project has been unlocked for edition.';
    var reloadDelayMs = typeof options.reloadDelayMs === 'number' ? options.reloadDelayMs : 2000;

    FormModals.bindAutoDismiss();

    if (release) {
        $('.btn_unlock').click(function () {
            _postMutexAction(release!, unlockMessage, reloadDelayMs, this as HTMLButtonElement);
            return false;
        });
    }

    if (acquire) {
        $('#btn_lock_project').click(function () {
            _postMutexAction(acquire!, lockMessage, 0, this as HTMLButtonElement);
            return false;
        });
    }
}
