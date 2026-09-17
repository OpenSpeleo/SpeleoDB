import { containDialogTab, getDialogFocusableElements } from './dialog_focus.js';

afterEach(() => { document.body.innerHTML = ''; });

it('includes summaries and excludes disabled, hidden, and collapsed disclosure controls', () => {
    document.body.innerHTML = `<section id="dialog" tabindex="-1">
        <h2 tabindex="-1">Settings</h2>
        <button id="first">Close</button>
        <details id="types"><summary id="summary">Types</summary><input id="type">
            <details><summary id="nested-summary">More</summary><input id="nested-type"></details>
        </details>
        <fieldset disabled><input id="disabled-type"></fieldset>
        <input type="hidden"><button hidden>Hidden</button><button style="display:none">Hidden style</button>
        <div inert><button>Inert</button></div><button tabindex="-2">Negative tab index</button>
        <button id="last">Done</button>
    </section>`;
    const dialog = document.getElementById('dialog');
    expect(getDialogFocusableElements(dialog).map(control => control.id)).toEqual(['first', 'summary', 'last']);
    document.getElementById('types').open = true;
    expect(getDialogFocusableElements(dialog).map(control => control.id))
        .toEqual(['first', 'summary', 'type', 'nested-summary', 'last']);
});

it('wraps both directions from a non-tabbable title and preserves ordinary traversal', () => {
    document.body.innerHTML = '<section id="dialog" tabindex="-1"><h2 tabindex="-1">Title</h2><button id="first">Close</button><input id="middle"><button id="last">Done</button></section>';
    const dialog = document.getElementById('dialog');
    for (const shiftKey of [false, true]) {
        dialog.querySelector('h2').focus();
        const event = new KeyboardEvent('keydown', { key: 'Tab', shiftKey, cancelable: true });
        containDialogTab(event, dialog);
        expect(event.defaultPrevented).toBe(true);
        expect(document.activeElement.id).toBe(shiftKey ? 'last' : 'first');
    }
    document.getElementById('middle').focus();
    const event = new KeyboardEvent('keydown', { key: 'Tab', cancelable: true });
    containDialogTab(event, dialog);
    expect(event.defaultPrevented).toBe(false);
    expect(document.activeElement.id).toBe('middle');
});

it('keeps focus on the dialog when it has no interactive controls', () => {
    document.body.innerHTML = '<section id="dialog" tabindex="-1"><h2 tabindex="-1">Empty</h2></section>';
    const dialog = document.getElementById('dialog');
    dialog.querySelector('h2').focus();
    const event = new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, cancelable: true });
    containDialogTab(event, dialog);
    expect(event.defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(dialog);
});
