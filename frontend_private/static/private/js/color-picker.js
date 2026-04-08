/**
 * Shared color-picker wiring for project and GPS-track forms.
 *
 * Call `initColorPicker(opts)` after the DOM is ready.  `opts` maps
 * logical roles to actual jQuery selectors so the same logic works
 * across pages with different element IDs.
 *
 * Required opts keys:
 *   preview      – color swatch element              (#color-preview)
 *   hiddenInput  – hidden <input name="color">       (#color-value)
 *   nativePicker – <input type="color">              (#color-picker)
 *   pickerBtn    – button that opens native picker   (#color-picker-btn)
 *   hexInput     – visible hex text input             (#color-hex-input)
 *   presets      – preset swatch buttons              (.color-preset)
 */

/* exported initColorPicker */

var _hexBodyRe = /^[0-9a-fA-F]{6}$/;

function initColorPicker(opts) {
    function setColor(hex) {
        var lower = hex.toLowerCase();
        $(opts.hiddenInput).val(lower);
        $(opts.nativePicker).val(lower);
        $(opts.preview).css('background-color', lower);
        $(opts.hexInput).val(lower.slice(1))
            .removeClass('border-rose-500')
            .addClass('border-slate-600');
        $(opts.presets)
            .removeClass('ring-2 ring-white ring-offset-2 ring-offset-slate-800');
        $(opts.presets + '[data-color="' + lower + '"]')
            .addClass('ring-2 ring-white ring-offset-2 ring-offset-slate-800');
    }

    $(opts.presets).click(function (e) {
        e.preventDefault();
        setColor($(this).data('color'));
    });

    $(opts.pickerBtn).click(function (e) {
        e.preventDefault();
        $(opts.nativePicker).click();
    });

    $(opts.nativePicker).on('input', function () {
        setColor($(this).val());
    });

    $(opts.hexInput).on('input', function () {
        var val = $(this).val().replace(/[^0-9a-fA-F]/g, '').slice(0, 6);
        $(this).val(val);
        if (_hexBodyRe.test(val)) {
            setColor('#' + val);
        } else {
            $(this).removeClass('border-slate-600').addClass('border-rose-500');
        }
    });

    return setColor;
}
