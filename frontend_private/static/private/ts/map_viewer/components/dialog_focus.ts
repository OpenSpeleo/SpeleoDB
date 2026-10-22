import { isVisibleMapElement } from './overlay_host.ts';

/** Elements participating in a dialog's keyboard order, including disclosures. */
export function getDialogFocusableElements(element: HTMLElement) {
    const controls = [...element.querySelectorAll<HTMLElement>('button, a[href], input, select, textarea, summary, [tabindex]')]
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
    // A radio group occupies one Tab stop; arrow keys select its other options.
    return controls.filter(control => {
        if (!(control instanceof HTMLInputElement) || control.type !== 'radio' || !control.name) return true;
        const group = controls.filter((candidate): candidate is HTMLInputElement => (
            candidate instanceof HTMLInputElement && candidate.type === 'radio'
            && candidate.name === control.name && candidate.form === control.form
        ));
        return control === (group.find(candidate => candidate.checked) || group[0]);
    });
}

/** Keep every Tab step inside the dialog, including Safari's reduced native tab order. */
export function containDialogTab(event: KeyboardEvent, element: HTMLElement) {
    if (event.key !== 'Tab') return;
    const controls = getDialogFocusableElements(element);
    const current = controls.indexOf(document.activeElement as HTMLElement);
    event.preventDefault();
    const target = current === -1
        ? (event.shiftKey ? controls.at(-1) : controls[0])
        : controls[(current + (event.shiftKey ? -1 : 1) + controls.length) % controls.length];
    // Match native Tab scrolling so focused controls remain visible in long dialogs.
    (target || element).focus();
}
