import { DepthLegend } from './depth_legend.js';
import { State, createDefaultDisplayPreferences } from '../state.js';
import { Layers } from '../map/layers.js';
import { Config } from '../config.js';

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

function initializeDepthLegend(limitFeet = null, unit = 'ft', measuredMaximum = 200) {
    State.projectDepthDomains.set('1', measuredMaximum === null ? null : { min: 0, max: measuredMaximum });
    Layers.setDepthLimit(limitFeet, unit);
    Layers.setColorMode('depth');
    const { map, handlers } = createMapMock();
    DepthLegend.init(map);
    return {
        map,
        handlers,
        hover(properties, source = 'project-geojson-1') {
            map.queryRenderedFeatures.mockReturnValue([{ layer: { type: 'line' }, source, properties }]);
            handlers.mousemove({ point: { x: 100, y: 100 } });
        },
    };
}

describe('DepthLegend', () => {
    beforeEach(() => {
        State.resetLayerState();
        State.displayPreferences = createDefaultDisplayPreferences();
        State.activeDepthDomain = null;
        State.map = null;
        Config._projects = [{ id: '1' }];
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

    it('starts with restored depth preferences and keeps the scale when station markers are hidden', () => {
        State.displayPreferences.colorMode = 'depth';
        State.activeDepthDomain = { min: 0, max: 80 };
        const { map } = createMapMock();
        DepthLegend.init(map);
        const legend = document.getElementById('depth-scale-fixed');
        expect(legend.style.display).toBe('block');
        expect(legend.textContent).toContain('80 ft');
        Layers.setCategoryVisibility('surveyStations', false);
        expect(legend.style.display).toBe('block');
        expect(State.activeDepthDomain).toEqual({ min: 0, max: 80 });
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

    it.each([
        [100, 'ft', '100 ft'],
        [100, 'm', '30.48 m'],
        [10.06, 'ft', '10.06 ft'],
        [1e-12, 'ft', '1e-12 ft'],
        [1e-12, 'm', '3.048e-13 m'],
    ])('shows the precise fixed maximum %s in %s', (maximum, unit, expected) => {
        const { hover } = initializeDepthLegend(maximum, unit);
        expect(document.getElementById('depth-scale-fixed').textContent).toContain(expected);
        hover({ depth_val: 200 });
        expect(document.getElementById('depth-cursor-label').textContent).toBe(expected);
        expect(document.getElementById('depth-cursor-indicator').style.left).toBe('calc(100% - 1px)');
    });

    it('uses the selected unit for unsaturated readings and preserves actual negative readings', () => {
        const { hover } = initializeDepthLegend(100, 'm');
        hover({ depth_val: 40 });
        expect(document.getElementById('depth-cursor-label').textContent).toBe('12.2 m');
        expect(document.getElementById('depth-cursor-indicator').style.left).toBe('calc(40% - 1px)');
        hover({ depth_val: -10 });
        expect(document.getElementById('depth-cursor-label').textContent).toBe('-3.0 m');
        expect(document.getElementById('depth-cursor-indicator').style.left).toBe('calc(0% - 1px)');
    });

    it('never rounds a displayed reading above the custom maximum', () => {
        const { hover } = initializeDepthLegend(1.06);
        hover({ depth_val: 1.059 });
        expect(document.getElementById('depth-cursor-label').textContent).toBe('1.06 ft');
    });

    it('preserves the public default axis rounding and unbounded raw readings', () => {
        const { hover } = initializeDepthLegend(null, 'ft', 80.2);
        expect(document.getElementById('depth-scale-fixed').textContent).toContain('81 ft');
        hover({ depth_val: 90 });
        expect(document.getElementById('depth-cursor-label').textContent).toBe('90.0 ft');
        expect(document.getElementById('depth-cursor-indicator').style.left).toBe('calc(100% - 1px)');
    });

    it('refreshes a stationary cursor on limit, unit and reset without querying the map again', () => {
        const { map, hover } = initializeDepthLegend(100);
        hover({ depth_val: 80 });
        expect(document.getElementById('depth-cursor-label').textContent).toBe('80.0 ft');
        Layers.setDepthLimit(50, 'ft');
        expect(document.getElementById('depth-cursor-label').textContent).toBe('50 ft');
        Layers.setDepthLimit(50, 'm');
        expect(document.getElementById('depth-cursor-label').textContent).toBe('15.24 m');
        expect(document.getElementById('depth-cursor-label').style.display).toBe('block');
        Layers.setDepthLimit(null, 'ft');
        expect(document.getElementById('depth-cursor-label').textContent).toBe('80.0 ft');
        expect(document.getElementById('depth-cursor-indicator').style.left).toBe('calc(40% - 1px)');
        expect(map.queryRenderedFeatures).toHaveBeenCalledTimes(1);
    });

    it('recovers legacy normalized readings from the cached project domain before clipping', () => {
        const { hover } = initializeDepthLegend(100);
        hover({ depth_norm: 0.75 });
        expect(document.getElementById('depth-cursor-label').textContent).toBe('100 ft');
        hover({ depth_norm: 0.25 });
        expect(document.getElementById('depth-cursor-label').textContent).toBe('50.0 ft');
        expect(document.getElementById('depth-cursor-indicator').style.left).toBe('calc(50% - 1px)');
    });

    it('keeps the legacy normalized fallback for a source without a project cache', () => {
        const { hover } = initializeDepthLegend(100);
        hover({ depth_norm: 0.25 }, 'unknown-source');
        expect(document.getElementById('depth-cursor-label').textContent).toBe('25.0 ft');
    });

    it.each([{ depth_val: null }, { depth_val: '' }, { depth_val: 'bad' }, {}])(
        'does not invent a cursor value for missing or invalid depth %s', properties => {
            const { hover } = initializeDepthLegend(100);
            hover(properties);
            expect(document.getElementById('depth-cursor-label').style.display).toBe('none');
        }
    );

    it('leaves unavailable depth N/A with a cap and recognizes measured zero depth', () => {
        const { hover } = initializeDepthLegend(100, 'm', null);
        expect(document.getElementById('depth-scale-fixed').textContent).toContain('N/A');
        hover({ depth_val: 40 });
        expect(document.getElementById('depth-cursor-label').style.display).toBe('none');
        State.projectDepthDomains.set('1', { min: 0, max: 0 });
        Layers.recomputeActiveDepthDomain();
        expect(document.getElementById('depth-scale-fixed').textContent).toContain('30.48 m');
        hover({ depth_val: 0 });
        expect(document.getElementById('depth-cursor-label').textContent).toBe('0.0 m');
    });

    it.each(['mouseout', 'colorMode', 'shotMode', 'visibility'])('clears cached hover on %s', trigger => {
        const { hover, handlers } = initializeDepthLegend(100);
        hover({ depth_val: 80 });
        if (trigger === 'mouseout') handlers.mouseout();
        if (trigger === 'colorMode') Layers.setColorMode('project');
        if (trigger === 'shotMode') Layers.setColorMode('shot');
        if (trigger === 'visibility') Layers.toggleProjectVisibility('1', false);
        expect(document.getElementById('depth-cursor-label').style.display).toBe('none');
        expect(DepthLegend.hoveredLineFeature).toBeNull();
        Layers.setDepthLimit(50, 'm');
        expect(document.getElementById('depth-cursor-label').style.display).toBe('none');
    });

    it.each(['toggle', 'preference', 'removed'])('clears stale project hover after %s while another project keeps the domain', change => {
        const { hover } = initializeDepthLegend(100);
        Config._projects.push({ id: '2' });
        State.projectDepthDomains.set('2', { min: 0, max: 400 });
        hover({ depth_val: 80 });
        if (change === 'toggle') Layers.toggleProjectVisibility('1', false);
        if (change === 'preference') {
            State.projectLayerStates.set('1', false);
            Layers.recomputeActiveDepthDomain();
        }
        if (change === 'removed') {
            State.projectDepthDomains.delete('1');
            Layers.recomputeActiveDepthDomain();
        }
        expect(State.activeDepthDomain).toEqual({ min: 0, max: 100 });
        expect(document.getElementById('depth-cursor-label').style.display).toBe('none');
        expect(DepthLegend.hoveredLineFeature).toBeNull();
    });
});
