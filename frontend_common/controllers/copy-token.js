import { afterWindowLoad } from '../readiness.js';

const CHECK_ICON = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>';
const COPY_ICON = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path>';

function copyFallback(value) {
    const $textArea = $('<textarea>').val(value).css({
        position: 'fixed',
        opacity: '0',
        left: '-9999px',
    }).appendTo('body');
    $textArea[0].select();
    $textArea[0].setSelectionRange(0, 99999);
    let success = false;
    try {
        success = document.execCommand('copy');
    } catch {
        success = false;
    } finally {
        $textArea.remove();
    }
    return Promise.resolve(success);
}

function attachCopyButton(options) {
    const $button = $(options.button);
    const $text = $(options.text);
    const $icon = options.icon ? $(options.icon) : $();

    function reset() {
        $text.text('Copy');
        if ($icon.length) $icon.html(COPY_ICON);
        if (options.toggleClasses) {
            $button.removeClass('bg-green-600 hover:bg-green-700')
                .addClass('bg-slate-700 hover:bg-slate-600');
        }
    }

    function success() {
        $text.text('Copied!');
        if ($icon.length) $icon.html(CHECK_ICON);
        if (options.toggleClasses) {
            $button.removeClass('bg-slate-700 hover:bg-slate-600')
                .addClass('bg-green-600 hover:bg-green-700');
        }
        window.setTimeout(reset, 2000);
    }

    $button.on('click', function (event) {
        event.preventDefault();
        event.stopPropagation();
        if (options.disabledGuard && $button.prop('disabled')) return;
        const value = $(options.value).text().trim();
        if (!value) return;
        const operation = navigator.clipboard?.writeText
            ? navigator.clipboard.writeText(value).then(() => true).catch(() => copyFallback(value))
            : copyFallback(value);
        operation.then(copied => {
            if (copied) success();
            else {
                $text.text('Failed');
                window.setTimeout(reset, 2000);
            }
        });
    });
}

function attachTokenModal(options) {
    const $form = $(options.form);
    const $modal = $(options.modal);
    let shouldSubmit = false;

    function show() {
        $modal.css('display', 'flex');
        $('body').css('overflow', 'hidden');
    }
    function hide() {
        $modal.hide();
        $('body').css('overflow', '');
    }

    $form.on('submit', function (event) {
        if (!shouldSubmit) {
            event.preventDefault();
            show();
        }
        shouldSubmit = false;
    });
    $(options.cancel).on('click', hide);
    $(options.confirm).on('click', function () {
        shouldSubmit = true;
        hide();
        if (options.namedSubmit) {
            const $submit = $('<button>', { type: 'submit', name: '_refresh_token' }).hide();
            $form.append($submit);
            window.setTimeout(() => $submit.trigger('click'), 100);
        } else {
            $form[0].submit();
        }
    });
    $modal.on('click', event => {
        if ($(event.target).is($modal)) hide();
    });
    $(document).on('keydown', event => {
        if (event.key === 'Escape' && $modal.is(':visible')) hide();
    });
}

export async function init(context) {
    if (context.waitForWindowLoad) await afterWindowLoad();
    context.copyButtons?.forEach(attachCopyButton);
    if (context.tokenModal) attachTokenModal(context.tokenModal);
}
