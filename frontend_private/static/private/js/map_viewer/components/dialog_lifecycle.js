import { getActiveMapDialog, getMapOverlayHost, isVisibleMapElement } from './overlay_host.js';
import { containDialogTab, getDialogFocusableElements } from './dialog_focus.js';

const dialogs = new Map();
let background = new Map();

function restoreBackground() {
    background.forEach((wasInert, element) => { element.inert = wasInert; });
    background = new Map();
}

function isolateDialog(element) {
    restoreBackground();
    for (let current = element; current?.parentElement; current = current.parentElement) {
        for (const sibling of current.parentElement.children) {
            if (sibling === current || !(sibling instanceof HTMLElement)) continue;
            background.set(sibling, sibling.inert);
            sibling.inert = true;
        }
    }
}

/** Open an existing map dialog; callers retain ownership of its content. */
export function openMapDialog(element, { closeButton = null, returnFocus = null, onClose = null, dismissOnBackdrop = true, canDismiss = () => true } = {}) {
    if (!element) return;
    if (dialogs.has(element) && !dialogs.get(element).canDismiss()) return;
    closeMapDialog(element, { restoreFocus: false });
    const trigger = returnFocus || document.activeElement;
    getMapOverlayHost().append(element);
    element.classList.remove('hidden');
    element.hidden = false;
    element.style.removeProperty('display');
    element.setAttribute('role', 'dialog');
    element.setAttribute('aria-modal', 'true');
    element.tabIndex = -1;
    const title = element.querySelector('h1, h2, h3');
    if (title) {
        if (!title.id) title.id = `${element.id}-title`;
        element.setAttribute('aria-labelledby', title.id);
    }
    const close = typeof closeButton === 'string' ? element.querySelector(closeButton) : closeButton;
    if (close) {
        close.setAttribute('aria-label', close.getAttribute('aria-label') || 'Close dialog');
        close.onclick = () => closeMapDialog(element);
    }
    element.onclick = event => {
        if (dismissOnBackdrop && event.target === element) closeMapDialog(element);
    };
    const keydown = event => {
        if (getActiveMapDialog() !== element) return;
        if (event.key === 'Escape') {
            event.preventDefault();
            event.stopImmediatePropagation();
            closeMapDialog(element);
        } else if (event.key === 'Tab') {
            containDialogTab(event, element);
        }
    };
    dialogs.set(element, { trigger, onClose, keydown, canDismiss });
    document.addEventListener('keydown', keydown, true);
    isolateDialog(element);
    (close || getDialogFocusableElements(element)[0] || element).focus({ preventScroll: true });
}

export function closeMapDialog(element, { restoreFocus = true } = {}) {
    if (!element) return;
    const record = dialogs.get(element);
    if (!record || !record.canDismiss()) return;
    dialogs.delete(element);
    document.removeEventListener('keydown', record.keydown, true);
    element.classList.add('hidden');
    restoreBackground();
    const parent = [...dialogs.keys()].findLast(isVisibleMapElement);
    if (parent) isolateDialog(parent);
    record.onClose?.();
    if (restoreFocus) {
        const triggerIsAvailable = record.trigger !== document.body && record.trigger !== document.documentElement
            && isVisibleMapElement(record.trigger) && !record.trigger.closest('[inert]');
        const target = triggerIsAvailable ? record.trigger
            : parent ? getDialogFocusableElements(parent)[0] || parent : document.getElementById('map-managers-button');
        target?.focus({ preventScroll: true });
    }
}
