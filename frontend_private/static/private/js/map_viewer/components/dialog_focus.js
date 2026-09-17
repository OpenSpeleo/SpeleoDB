import { isVisibleMapElement } from './overlay_host.js';

/** Elements participating in a dialog's keyboard order, including disclosures. */
export function getDialogFocusableElements(element) {
    return [...element.querySelectorAll('button, a[href], input, select, textarea, summary, [tabindex]')]
        .filter(control => {
            if (control.matches(':disabled, input[type="hidden"]')
                || (control.hasAttribute('tabindex') && control.tabIndex < 0)
                || control.closest('[inert]') || !isVisibleMapElement(control)) return false;
            for (let parent = control.parentElement; parent && parent !== element; parent = parent.parentElement) {
                if (!parent.matches('details:not([open])')) continue;
                const summary = [...parent.children].find(child => child.tagName === 'SUMMARY');
                if (!summary?.contains(control)) return false;
            }
            return true;
        });
}

/** Keep Tab inside the dialog even when initial focus is a non-tabbable title. */
export function containDialogTab(event, element) {
    if (event.key !== 'Tab') return;
    const controls = getDialogFocusableElements(element);
    const current = controls.indexOf(document.activeElement);
    if (current === -1 || (event.shiftKey && current === 0)
        || (!event.shiftKey && current === controls.length - 1)) {
        event.preventDefault();
        const target = event.shiftKey ? controls.at(-1) : controls[0];
        (target || element).focus({ preventScroll: true });
    }
}
