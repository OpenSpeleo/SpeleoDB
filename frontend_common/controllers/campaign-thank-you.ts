const initializedButtons = new WeakSet<HTMLButtonElement>();

/** data-thanks-* hooks connect the optional high-five to its local, text-only reply. */
export function init(_context: unknown, element: HTMLElement): void {
    const root = element.closest<HTMLElement>('.thanks-page');
    const button = root?.querySelector<HTMLButtonElement>('[data-thanks-high-five]');
    const status = root?.querySelector<HTMLElement>('[data-thanks-status]');
    const echo = root?.querySelector<HTMLElement>('[data-thanks-echo]');
    if (!root || !button || !status || !echo || initializedButtons.has(button)) return;

    button.addEventListener('click', () => {
        status.textContent = button.dataset.reply ?? '';
        root.classList.add('is-celebrating');
    });
    echo.addEventListener('animationend', () => {
        root.classList.remove('is-celebrating');
    });
    initializedButtons.add(button);
    button.hidden = false;
}
