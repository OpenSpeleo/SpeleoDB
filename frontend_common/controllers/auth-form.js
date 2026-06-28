import {
    attachAuthForm,
    validateEmail,
} from '../../frontend_public/static/js/auth_form.js';
import { afterWindowLoad } from '../readiness.js';

function emailValidator(payload) {
    if (!payload.email || !validateEmail(payload.email)) {
        return 'The Email Address is not valid !';
    }
    return null;
}

function passwordPairValidator(payload) {
    if (!payload.password || !payload.password2) {
        return 'One of the `password` fields is empty !';
    }
    if (payload.password !== payload.password2) {
        return 'Password fields do not match !';
    }
    return null;
}

function configureLogin(context) {
    attachAuthForm({
        formId: context.formId,
        endpoint: context.endpoint,
        onSuccess: () => {
            window.location.href = context.successRedirect;
        },
        validators: [payload => emailValidator(payload) || (
            payload.password ? null : 'The Password field is empty !'
        )],
        errorHandler: xhr => {
            if (xhr.status !== 401 || !xhr.responseJSON?.data) return null;
            const needsVerification = (xhr.responseJSON.data.flows || [])
                .some(flow => flow.id === 'verify_email');
            return needsVerification
                ? 'Your email is not verified. We just resent you an activation link on your email.'
                : 'Your account is inactive. If you believe this is an error, please contact us.';
        },
    });
}

function configureSignup(context) {
    attachAuthForm({
        formId: context.formId,
        endpoint: context.endpoint,
        successMessage: context.successMessage,
        treat401AsSuccess: true,
        beforeAjax: (payload, formData) => {
            const marker = (payload.cave_marker || '').trim().toUpperCase();
            if (marker !== 'ARROW') {
                $('#cave_diver_modal').show();
                return false;
            }
            formData.delete('cave_marker');
            delete payload.cave_marker;
            return true;
        },
        validators: [payload => {
            if (!payload.name) return 'The `name` field is empty !';
            return emailValidator(payload) || passwordPairValidator(payload);
        }],
    });

    $('#cave_diver_modal_close').click(() => $('#cave_diver_modal').hide());
    $(window).click(event => {
        if ($(event.target).is('#cave_diver_modal')) $('#cave_diver_modal').hide();
    });
}

function configurePasswordReset(context) {
    attachAuthForm({
        formId: context.formId,
        endpoint: context.endpoint,
        successMessage: context.successMessage,
        validators: [emailValidator],
    });
}

function configurePasswordResetFromKey(context) {
    attachAuthForm({
        formId: context.formId,
        endpoint: context.endpoint,
        successMessage: context.successMessage,
        treat401AsSuccess: true,
        validators: [passwordPairValidator],
    });
}

const initializers = {
    login: configureLogin,
    signup: configureSignup,
    'password-reset': configurePasswordReset,
    'password-reset-from-key': configurePasswordResetFromKey,
};

export async function init(context) {
    await afterWindowLoad();
    const initialize = initializers[context.mode];
    if (!initialize) throw new Error(`Unsupported auth form mode: ${context.mode}`);
    initialize(context);
}
