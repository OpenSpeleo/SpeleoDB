// @vitest-environment node

import { readFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';

describe('JSDOM window runtime compatibility', () => {
    it.each([undefined, 'outside-only'])('preserves window events with runScripts=%s', runScripts => {
        const dom = new JSDOM('<button>Click</button><iframe></iframe>', { runScripts });
        try {
            const { window } = dom;
            const listener = vi.fn();
            window.addEventListener('probe', listener);
            window.dispatchEvent(new window.Event('probe'));
            expect(listener).toHaveBeenCalledExactlyOnceWith(expect.objectContaining({ target: window }));
            window.removeEventListener('probe', listener);
            window.dispatchEvent(new window.Event('probe'));
            expect(listener).toHaveBeenCalledTimes(1);

            const bubbled = vi.fn();
            window.addEventListener('click', bubbled);
            window.document.querySelector('button').click();
            expect(bubbled).toHaveBeenCalledTimes(1);

            const frame = window.document.querySelector('iframe').contentWindow;
            const frameListener = vi.fn();
            frame.addEventListener('probe', frameListener);
            frame.dispatchEvent(new frame.Event('probe'));
            expect(frameListener).toHaveBeenCalledExactlyOnceWith(expect.objectContaining({ target: frame }));
            expect(listener).toHaveBeenCalledTimes(1);

            for (const forged of [{}, Object.create(window)]) {
                expect(() => window.EventTarget.prototype.addEventListener.call(forged, 'probe', listener))
                    .toThrow(/not a valid instance of EventTarget/);
            }
        } finally {
            dom.window.close();
        }
    });

    it('shares window listeners between evaluated scripts and vendored jQuery', () => {
        const dom = new JSDOM('', { runScripts: 'outside-only' });
        try {
            const { window } = dom;
            window.eval('window.received = 0; window.addEventListener("probe", () => window.received++);');
            window.eval(readFileSync(new URL('../../frontend_public/static/js/vendors/jquery-3.7.1.js', import.meta.url), 'utf8'));
            const listener = vi.fn();
            window.jQuery(window).on('probe', listener);
            window.dispatchEvent(new window.Event('probe'));
            expect(window.received).toBe(1);
            expect(listener).toHaveBeenCalledTimes(1);
            window.jQuery(window).off('probe', listener);
        } finally {
            dom.window.close();
        }
    });
});
