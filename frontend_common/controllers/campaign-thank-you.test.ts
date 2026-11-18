import { init } from './campaign-thank-you.ts';

afterEach(() => { document.body.innerHTML = ''; });

it('offers the high-five only after wiring and announces the configured reply as text', () => {
    document.body.innerHTML = `
        <main class="thanks-page">
            <button type="button" data-thanks-high-five hidden></button>
            <p data-thanks-status role="status"></p>
            <span data-thanks-echo aria-hidden="true"></span>
            <script type="application/json">{}</script>
        </main>`;
    const root = document.querySelector<HTMLElement>('.thanks-page')!;
    const button = root.querySelector<HTMLButtonElement>('button')!;
    const status = root.querySelector<HTMLElement>('[role="status"]')!;
    const echo = root.querySelector<HTMLElement>('[data-thanks-echo]')!;
    const reply = 'Muddy high-five! <img src=x onerror="bad()">';
    button.dataset.reply = reply;

    expect(button.hidden).toBe(true);
    init({}, root.querySelector('script')!);
    expect(button.hidden).toBe(false);
    button.click();
    expect(status.textContent).toBe(reply);
    expect(status.querySelector('img')).toBeNull();

    // The browser's CSS animation completion permits another high-five.
    echo.dispatchEvent(new Event('animationend', { bubbles: true }));
    button.dataset.reply = 'Another high-five, still muddy.';
    button.click();
    expect(status.textContent).toBe('Another high-five, still muddy.');
    expect(document.activeElement).not.toBe(status);
});
