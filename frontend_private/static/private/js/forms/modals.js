/**
 * Shared helpers for the `modal_success` / `modal_error` / `modal_confirmation`
 * snippets that every private page includes.
 *
 * Lets templates stop hand-rolling `body.click` / `$('#modal_success').hide()`
 * wiring.  Usage:
 *
 *   FormModals.bindAutoDismiss();
 *   FormModals.showSuccess('It worked.');
 *   FormModals.showError('Something broke.');
 *
 * Requires: jQuery.
 */

/* exported FormModals */

var FormModals = (function () {
    function hideAll() {
        $('#modal_success').hide();
        $('#modal_error').hide();
        $('#modal_confirmation').hide();
    }

    function bindAutoDismiss() {
        // jQuery's `:visible` does not work under JSDOM (no real layout), and
        // `.hide()` on an already-hidden element is a harmless no-op, so just
        // call it unconditionally. Using native display checks here would be
        // brittle with `style` vs computed display.
        $('body').click(function () {
            $('#modal_success').hide();
            $('#modal_error').hide();
            $('#modal_confirmation').hide();
        });
    }

    function showSuccess(htmlText) {
        $('#modal_success_txt').html(htmlText);
        $('#modal_success').css('display', 'flex');
    }

    function showError(htmlText) {
        $('#modal_error_txt').html(htmlText);
        $('#modal_error').css('display', 'flex');
    }

    function showConfirmation() {
        $('#modal_confirmation').css('display', 'flex');
    }

    function hideConfirmation() {
        $('#modal_confirmation').hide();
    }

    return {
        bindAutoDismiss: bindAutoDismiss,
        hideAll: hideAll,
        showSuccess: showSuccess,
        showError: showError,
        showConfirmation: showConfirmation,
        hideConfirmation: hideConfirmation,
    };
})();
