import { escapeHtml } from '../../frontend_private/static/private/ts/xss-helpers.ts';
import { afterWindowLoad } from '../readiness.ts';
import { FormModals } from '../../frontend_private/static/private/ts/forms/modals.ts';
import type { FeedbackContext, FeedbackFailurePayload } from '../../ts-types/controllers/feedback.ts';

export async function init(context: FeedbackContext) {
    await afterWindowLoad();
    FormModals.bindAutoDismiss();

    $('.feedback_score').on('click', function () {
        $('.feedback_score').removeClass('bg-indigo-500 border-indigo-500')
            .addClass('bg-slate-800 border-slate-500');
        $(this).removeClass('bg-slate-800 border-slate-500')
            .addClass('bg-indigo-500 border-indigo-500');
        $('input[name=score]').val($(this).data('score') as number | string);
    });

    const form = document.getElementById('feedback_form') as HTMLFormElement;
    // eslint-disable-next-line @typescript-eslint/no-misused-promises -- Preserve the existing async listener and its internal submission catch.
    document.getElementById('btn_submit')!.addEventListener('click', async event => {
        event.preventDefault();
        try {
            const response = await fetch(context.endpoint, {
                method: form.method,
                body: new FormData(form),
                headers: { Accept: 'application/json' },
            });
            const data = await response.json() as FeedbackFailurePayload;
            if (response.ok) {
                form.reset();
                FormModals.showSuccess('Thanks for your feedback. We appreciate a lot!');
                return;
            }
            const message = Object.hasOwn(data, 'errors')
                ? data.errors!.map(error => error.message).join(', ')
                : 'Oops! There was a problem submitting your feedback';
            FormModals.showError(escapeHtml(message));
        } catch {
            FormModals.showError('Oops! There was a problem submitting your feedback');
        }
    });
}
