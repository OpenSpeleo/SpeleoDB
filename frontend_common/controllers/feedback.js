import { afterWindowLoad } from '../readiness.js';
import { FormModals } from '../../frontend_private/static/private/js/forms/modals.js';

export async function init(context) {
    await afterWindowLoad();
    FormModals.bindAutoDismiss();

    $('.feedback_score').on('click', function () {
        $('.feedback_score').removeClass('bg-indigo-500 border-indigo-500')
            .addClass('bg-slate-800 border-slate-500');
        $(this).removeClass('bg-slate-800 border-slate-500')
            .addClass('bg-indigo-500 border-indigo-500');
        $('input[name=score]').val($(this).data('score'));
    });

    const form = document.getElementById('feedback_form');
    document.getElementById('btn_submit').addEventListener('click', async event => {
        event.preventDefault();
        try {
            const response = await fetch(context.endpoint, {
                method: form.method,
                body: new FormData(form),
                headers: { Accept: 'application/json' },
            });
            const data = await response.json();
            if (response.ok) {
                form.reset();
                FormModals.showSuccess('Thanks for your feedback. We appreciate a lot!');
                return;
            }
            const message = Object.hasOwn(data, 'errors')
                ? data.errors.map(error => error.message).join(', ')
                : 'Oops! There was a problem submitting your feedback';
            FormModals.showError(message);
        } catch {
            FormModals.showError('Oops! There was a problem submitting your feedback');
        }
    });
}
