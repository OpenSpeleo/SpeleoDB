import { positionOverlayPanel } from './panel_position.ts';
import { DEFAULTS } from '../config.ts';

beforeEach(() => { document.body.innerHTML = '<div id="container"><div id="first"></div><div id="second"></div><div id="panel"></div></div>'; });
afterEach(() => { document.body.innerHTML = ''; });

it('uses the first anchor not explicitly hidden by display and preserves panel identity', () => {
    const container = document.getElementById('container')!;
    const first = document.getElementById('first')!;
    const second = document.getElementById('second')!;
    const panel = document.getElementById('panel')!;
    first.style.display = 'none';
    second.hidden = true;
    vi.spyOn(container, 'getBoundingClientRect').mockReturnValue({ top: 20 } as DOMRect);
    vi.spyOn(second, 'getBoundingClientRect').mockReturnValue({ bottom: 100 } as DOMRect);
    expect(positionOverlayPanel([null, panel], ['missing', 'first', 'second'], container)).toBeUndefined();
    expect(panel.style.top).toBe(`${80 + DEFAULTS.UI.MAP_PANEL_GAP_PX}px`);
    expect(panel.style.left).toBe(`${DEFAULTS.UI.MAP_PANEL_EDGE_PX}px`);
    expect(panel.style.right).toBe('auto');
    expect(document.getElementById('panel')!).toBe(panel);
});

it('uses the configured edge when no anchor exists and leaves elements alone without a container', () => {
    const panel = document.getElementById('panel')!;
    expect(positionOverlayPanel([panel], [], null)).toBeUndefined();
    expect(panel.style.top).toBe('');
    positionOverlayPanel([panel], ['missing'], document.getElementById('container'));
    expect(panel.style.top).toBe(`${DEFAULTS.UI.MAP_PANEL_EDGE_PX}px`);
});
