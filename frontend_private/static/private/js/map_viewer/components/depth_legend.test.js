import { DepthLegend } from './depth_legend.js';

function createMapMock() {
    const handlers = {};
    const map = {
        on: vi.fn((eventName, handler) => {
            handlers[eventName] = handler;
        }),
        off: vi.fn((eventName) => {
            delete handlers[eventName];
        }),
        queryRenderedFeatures: vi.fn(() => [])
    };
    return { map, handlers };
}

describe('DepthLegend', () => {
    beforeEach(() => {
        document.body.innerHTML = '<div id="map"></div>';
    });

    afterEach(() => {
        DepthLegend.destroy();
        document.body.innerHTML = '';
    });

    it('shows N/A labels when in depth mode with no active domain', () => {
        const { map } = createMapMock();
        DepthLegend.init(map);

        window.dispatchEvent(new CustomEvent('speleo:color-mode-changed', { detail: { mode: 'depth' } }));
        window.dispatchEvent(new CustomEvent('speleo:depth-domain-updated', {
            detail: { domain: null, available: false, max: null }
        }));

        const legend = document.getElementById('depth-scale-fixed');
        expect(legend).not.toBeNull();
        expect(legend.style.display).toBe('block');
        expect(legend.textContent).toContain('N/A');
    });

    it('updates gauge labels when depth domain max changes', () => {
        const { map } = createMapMock();
        DepthLegend.init(map);

        window.dispatchEvent(new CustomEvent('speleo:color-mode-changed', { detail: { mode: 'depth' } }));
        window.dispatchEvent(new CustomEvent('speleo:depth-domain-updated', {
            detail: { domain: { min: 0, max: 80 }, available: true, max: 80 }
        }));
        expect(document.getElementById('depth-scale-fixed').textContent).toContain('80 ft');

        window.dispatchEvent(new CustomEvent('speleo:depth-domain-updated', {
            detail: { domain: { min: 0, max: 25 }, available: true, max: 25 }
        }));
        expect(document.getElementById('depth-scale-fixed').textContent).toContain('25 ft');
    });

    it('updates cursor position and label on mouse move with line depth', () => {
        const { map, handlers } = createMapMock();
        DepthLegend.init(map);

        window.dispatchEvent(new CustomEvent('speleo:color-mode-changed', { detail: { mode: 'depth' } }));
        window.dispatchEvent(new CustomEvent('speleo:depth-domain-updated', {
            detail: { domain: { min: 0, max: 80 }, available: true, max: 80 }
        }));

        map.queryRenderedFeatures.mockReturnValue([
            {
                layer: { type: 'line' },
                properties: { depth_val: 40 }
            }
        ]);

        handlers.mousemove({ point: { x: 100, y: 100 } });

        const cursor = document.getElementById('depth-cursor-indicator');
        const label = document.getElementById('depth-cursor-label');
        expect(cursor.style.display).toBe('block');
        expect(label.style.display).toBe('block');
        expect(label.textContent).toBe('40.0 ft');
    });
});

