import type { AdminCampaignPreviewContext } from '../../ts-types/controllers/admin-campaign-preview.ts';

function sameOriginUrl(value: unknown): URL | null {
    if (typeof value !== 'string') return null;
    try {
        const url = new URL(value, window.location.href);
        return url.origin === window.location.origin && ['http:', 'https:'].includes(url.protocol) ? url : null;
    } catch {
        return null;
    }
}

/**
 * Saves the campaign through its native admin form and requests a preview.
 * Widgets expose data-campaign-save-preview and matching
 * data-campaign-preview-status hooks using their template field names.
 */
export function init(context: AdminCampaignPreviewContext) {
    const form = document.getElementById(context.formId);
    if (!(form instanceof HTMLFormElement)) return;
    const buttons = Array.from(form.querySelectorAll<HTMLButtonElement>('[data-campaign-save-preview], [name="_preview_pdf"]'));
    const dialog = document.querySelector<HTMLDialogElement>('[data-campaign-preview-dialog]');
    dialog?.querySelector<HTMLButtonElement>('[data-campaign-preview-close]')?.addEventListener('click', () => {
        dialog.close();
    });
    let pending = false;

    // The PDF button remains a native submit control; these hooks report save errors.
    form.addEventListener('submit', event => {
        if (!(event.submitter instanceof HTMLButtonElement) || event.submitter.name !== '_preview_pdf') return;
        event.preventDefault();
        if (pending || !form.reportValidity()) return;
        const status = form.querySelector<HTMLElement>('[data-campaign-pdf-status]');
        if (!status) return;
        // Open during the user gesture so browsers do not block the saved PDF tab.
        const tab = window.open('about:blank', '_blank');
        if (!tab) {
            status.textContent = 'Allow pop-ups for this site, then try again.';
            return;
        }
        tab.opener = null;
        const body = new FormData(form);
        body.set('_preview_pdf', '1');
        const disabledStates = buttons.map(item => item.disabled);
        pending = true;
        buttons.forEach(item => { item.disabled = true; });
        status.textContent = 'Saving and opening PDF…';
        status.setAttribute('aria-busy', 'true');
        void (async () => {
            try {
                const response = await fetch(form.action || window.location.href, {
                    method: 'POST', body, credentials: 'same-origin',
                    headers: { Accept: 'application/json' },
                });
                const payload: unknown = await response.json();
                if (!payload || typeof payload !== 'object') throw new Error('Invalid save response');
                const data = payload as Record<string, unknown>;
                if (!response.ok) {
                    const errors = data.errors && typeof data.errors === 'object'
                        ? Object.values(data.errors).flat().filter(item => typeof item === 'string')
                        : [];
                    status.textContent = [typeof data.message === 'string' ? data.message : 'Could not save the draft.', ...errors].join(' ');
                    tab.close();
                    return;
                }
                const changeUrl = sameOriginUrl(data.change_url);
                const pdfUrl = sameOriginUrl(data.pdf_url);
                if (!changeUrl || !pdfUrl) throw new Error('Invalid save response');
                if (!tab.closed) tab.location.replace(pdfUrl.href);
                window.location.assign(changeUrl.href);
            } catch {
                tab.close();
                status.textContent = 'Could not confirm the save. Your edits are still on this page.';
            } finally {
                pending = false;
                buttons.forEach((item, index) => { item.disabled = disabledStates[index] ?? false; });
                status.setAttribute('aria-busy', 'false');
            }
        })();
    });

    const requestPreview = async (button: HTMLButtonElement) => {
        if (pending) return;
        const kind = button.dataset.campaignSavePreview;
        if (!kind) return;
        const status = form.querySelector<HTMLElement>(`[data-campaign-preview-status="${CSS.escape(kind)}"]`);
        if (!status) return;
        const reminder = form.querySelector<HTMLSelectElement>('[name="reminder_email_template"]');
        const reminderRequired = reminder?.required;
        let valid: boolean;
        try {
            if (kind === 'reminder_email_template' && reminder) reminder.required = true;
            valid = form.reportValidity();
        } finally {
            if (reminder && reminderRequired !== undefined) reminder.required = reminderRequired;
        }
        if (!valid) {
            status.textContent = 'Complete the required campaign fields and correct invalid values before requesting a preview.';
            return;
        }

        const body = new FormData(form);
        body.set('_save_preview', kind);
        const csrfToken = body.get('csrfmiddlewaretoken');
        const headers: Record<string, string> = { Accept: 'application/json' };
        if (typeof csrfToken === 'string') headers['X-CSRFToken'] = csrfToken;
        const disabledStates = buttons.map(item => item.disabled);
        pending = true;
        buttons.forEach(item => { item.disabled = true; });
        status.setAttribute('aria-busy', 'true');
        status.textContent = 'Saving and requesting preview…';
        try {
            const response = await fetch(form.action || window.location.href, {
                method: 'POST', body, headers, credentials: 'same-origin',
            });
            if (response.status === 403) {
                status.textContent = 'You do not have permission to request this preview.';
                return;
            }
            const payload: unknown = await response.json();
            if (!payload || typeof payload !== 'object') throw new Error('Invalid preview response');
            const data = payload as Record<string, unknown>;
            if (!response.ok) {
                const errors = data.errors && typeof data.errors === 'object'
                    ? Object.entries(data.errors).flatMap(([field, messages]) => Array.isArray(messages)
                        ? messages.filter((message): message is string => typeof message === 'string').map(message => `${field}: ${message}`)
                        : [])
                    : [];
                status.textContent = [typeof data.message === 'string' ? data.message : 'Could not confirm the preview request.', ...errors].join(' ');
                return;
            }
            const changeUrl = sameOriginUrl(data.change_url);
            if (!changeUrl || typeof data.message !== 'string') throw new Error('Invalid preview response');
            const wasAddForm = new URL(form.action || window.location.href).pathname.endsWith('/add/');
            form.action = changeUrl.href;
            if (wasAddForm) window.history.replaceState(null, '', changeUrl.href);
            status.textContent = data.message;
            const taskUrl = sameOriginUrl(data.task_results_url);
            if (taskUrl) {
                const link = document.createElement('a');
                link.href = taskUrl.href;
                link.textContent = 'View delivery status';
                status.append(' ', link);
            }
            const dialogMessage = dialog?.querySelector<HTMLElement>('[data-campaign-preview-message]');
            if (dialog && dialogMessage) {
                dialogMessage.textContent = data.message;
                const taskLink = dialog.querySelector<HTMLAnchorElement>('[data-campaign-preview-task]');
                if (taskLink) {
                    taskLink.hidden = !taskUrl;
                    if (taskUrl) taskLink.href = taskUrl.href;
                    else taskLink.removeAttribute('href');
                }
                if (!dialog.open) dialog.showModal();
            }
        } catch {
            status.textContent = 'Could not confirm the preview request. Your edits are still on this page.';
        } finally {
            pending = false;
            buttons.forEach((item, index) => { item.disabled = disabledStates[index] ?? false; });
            status.setAttribute('aria-busy', 'false');
        }
    };

    buttons.forEach(button => {
        button.addEventListener('click', () => { void requestPreview(button); });
        // The PDF submit must stay disabled until its interception is installed.
        if (button.name === '_preview_pdf') button.disabled = false;
    });
}
