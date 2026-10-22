import { containDialogTab, getDialogFocusableElements } from './dialog_focus.ts';

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
    const dialog = document.getElementById('dialog')!;
    expect(getDialogFocusableElements(dialog).map(control => control.id)).toEqual(['first', 'summary', 'last']);
    (document.getElementById('types') as HTMLDetailsElement).open = true;
    expect(getDialogFocusableElements(dialog).map(control => control.id))
        .toEqual(['first', 'summary', 'type', 'nested-summary', 'last']);
});

it('wraps both directions from a non-tabbable title and explicitly advances every Tab step', () => {
    document.body.innerHTML = '<section id="dialog" tabindex="-1"><h2 tabindex="-1">Title</h2><button id="first">Close</button><input id="middle"><button id="last">Done</button></section>';
    const dialog = document.getElementById('dialog')!;
    for (const shiftKey of [false, true]) {
        dialog.querySelector<HTMLElement>('h2')!.focus();
        const event = new KeyboardEvent('keydown', { key: 'Tab', shiftKey, cancelable: true });
        containDialogTab(event, dialog);
        expect(event.defaultPrevented).toBe(true);
        expect(document.activeElement!.id).toBe(shiftKey ? 'last' : 'first');
    }
    document.getElementById('middle')!.focus();
    const event = new KeyboardEvent('keydown', { key: 'Tab', cancelable: true });
    containDialogTab(event, dialog);
    expect(event.defaultPrevented).toBe(true);
    expect(document.activeElement!.id).toBe('last');
    containDialogTab(new KeyboardEvent('keydown', { key: 'Tab', cancelable: true }), dialog);
    expect(document.activeElement!.id).toBe('first');
    containDialogTab(new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, cancelable: true }), dialog);
    expect(document.activeElement!.id).toBe('last');
    containDialogTab(new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, cancelable: true }), dialog);
    expect(document.activeElement!.id).toBe('middle');
});

it('keeps focus on the dialog when it has no interactive controls', () => {
    document.body.innerHTML = '<section id="dialog" tabindex="-1"><h2 tabindex="-1">Empty</h2></section>';
    const dialog = document.getElementById('dialog')!;
    dialog.querySelector<HTMLElement>('h2')!.focus();
    const event = new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, cancelable: true });
    containDialogTab(event, dialog);
    expect(event.defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(dialog);
});

it('keeps one Tab stop per radio group and respects checked, disabled, and separate form controls', () => {
    document.body.innerHTML = `<section id="dialog">
        <form><input id="project" type="radio" name="color"><input id="depth" type="radio" name="color" checked>
            <input id="hidden" type="radio" name="units" checked hidden><input id="disabled" type="radio" name="units" disabled>
            <input id="feet" type="radio" name="units"><input id="meters" type="radio" name="units">
        </form>
        <form><input id="other-form" type="radio" name="color"></form>
        <input id="unnamed-one" type="radio"><input id="unnamed-two" type="radio">
        <button id="last">Done</button>
    </section>`;
    const dialog = document.getElementById('dialog')!;
    expect(getDialogFocusableElements(dialog).map(control => control.id))
        .toEqual(['depth', 'feet', 'other-form', 'unnamed-one', 'unnamed-two', 'last']);
    const project = document.getElementById('project') as HTMLInputElement;
    project.checked = true;
    project.focus();
    containDialogTab(new KeyboardEvent('keydown', { key: 'Tab', cancelable: true }), dialog);
    expect(document.activeElement!.id).toBe('feet');
    containDialogTab(new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, cancelable: true }), dialog);
    expect(document.activeElement!.id).toBe('project');
    const arrow = new KeyboardEvent('keydown', { key: 'ArrowRight', cancelable: true });
    containDialogTab(arrow, dialog);
    expect(arrow.defaultPrevented).toBe(false);
});
