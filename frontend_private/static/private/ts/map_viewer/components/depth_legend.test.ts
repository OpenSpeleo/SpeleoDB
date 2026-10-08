import type { DepthUnit } from '../../../../../../ts-types/domain/map-display.ts';
import type { LegendFeature, LegendMap, LegendPointerEvent } from '../../../../../../ts-types/domain/map-depth-legend.ts';
import { DepthLegend } from './depth_legend.ts';
import { State, createDefaultDisplayPreferences } from '../state.ts';
import { Layers } from '../map/layers.ts';
import { Config } from '../config.ts';

function createMapMock() {
    const handlers: Partial<{ mousemove: (event: LegendPointerEvent) => void; mouseout: () => void }> = {};
    const map = {
        on: vi.fn<LegendMap['on']>((eventName, handler) => {
            // The mouseout callback ignores its event; retain the original callback identity.
            handlers[eventName] = handler as ((event: LegendPointerEvent) => void) & (() => void);
        }),
        off: vi.fn<NonNullable<LegendMap['off']>>((eventName) => {
            delete handlers[eventName];
        }),
        queryRenderedFeatures: vi.fn<LegendMap['queryRenderedFeatures']>(() => [])
    };
    return { map, handlers };
}

async function initializeDepthLegend(limitFeet: number | null = null, unit: string = 'ft', measuredMaximum: number | null = 200) {
    State.projectDepthDomains.set('1', measuredMaximum === null ? null : { min: 0, max: measuredMaximum });
    Layers.setDepthLimit(limitFeet, unit);
    await Layers.setColorMode('depth');
    const { map, handlers } = createMapMock();
    DepthLegend.init(map);
    return {
        map,
        handlers,
        hover(this: void, properties: NonNullable<LegendFeature['properties']>, source = 'project-geojson-1') {
            map.queryRenderedFeatures.mockReturnValue([{ layer: { type: 'line' }, source, properties }]);
            handlers.mousemove!({ point: { x: 100, y: 100 } });
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

    it('shows N/A labels when in depth mode with no active domain', async () => {
        const { map } = createMapMock();
        DepthLegend.init(map);

        window.dispatchEvent(new CustomEvent('speleo:color-mode-changed', { detail: { mode: 'depth' } }));
        window.dispatchEvent(new CustomEvent('speleo:depth-domain-updated', {
            detail: { domain: null, available: false, max: null }
        }));

        const legend = document.getElementById('depth-scale-fixed')!;
        expect(legend).not.toBeNull();
        expect(legend.style.display).toBe('block');
        expect(legend.textContent).toContain('N/A');
    });

    it('starts with restored depth preferences and keeps the scale when station markers are hidden', async () => {
        State.displayPreferences.colorMode = 'depth';
        State.activeDepthDomain = { min: 0, max: 80 };
        const { map } = createMapMock();
        DepthLegend.init(map);
        const legend = document.getElementById('depth-scale-fixed')!;
        expect(legend.style.display).toBe('block');
        expect(legend.textContent).toContain('80 ft');
        await Layers.setCategoryVisibility('surveyStations', false);
        expect(legend.style.display).toBe('block');
        expect(State.activeDepthDomain).toEqual({ min: 0, max: 80 });
    });

    it('withholds the legend after partial application failure until a successful retry', async () => {
        await initializeDepthLegend();
        const legend = document.getElementById('depth-scale-fixed')!;
        expect(legend.style.display).toBe('block');
        State.displayUpdatePending = true;
        window.dispatchEvent(new CustomEvent('speleo:display-update-pending'));
        State.displayUpdatePending = false;
        window.dispatchEvent(new CustomEvent('speleo:display-update-failed'));
        window.dispatchEvent(new CustomEvent('speleo:depth-domain-updated', {
            detail: { domain: { min: 0, max: 80 } },
        }));
        expect(legend.style.display).toBe('none');
        await Layers.setColorMode('depth');
        expect(legend.style.display).toBe('block');
    });

    it('updates gauge labels when depth domain max changes', async () => {
        const { map } = createMapMock();
        DepthLegend.init(map);

        window.dispatchEvent(new CustomEvent('speleo:color-mode-changed', { detail: { mode: 'depth' } }));
        window.dispatchEvent(new CustomEvent('speleo:depth-domain-updated', {
            detail: { domain: { min: 0, max: 80 }, available: true, max: 80 }
        }));
        expect(document.getElementById('depth-scale-fixed')!.textContent).toContain('80 ft');

        window.dispatchEvent(new CustomEvent('speleo:depth-domain-updated', {
            detail: { domain: { min: 0, max: 25 }, available: true, max: 25 }
        }));
        expect(document.getElementById('depth-scale-fixed')!.textContent).toContain('25 ft');
    });

    it('updates cursor position and label on mouse move with line depth', async () => {
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

        handlers.mousemove!({ point: { x: 100, y: 100 } });

        const cursor = document.getElementById('depth-cursor-indicator')!;
        const label = document.getElementById('depth-cursor-label')!;
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
    ])('shows the precise fixed maximum %s in %s', async (maximum, unit, expected) => {
        const { hover } = await initializeDepthLegend(maximum, unit);
        expect(document.getElementById('depth-scale-fixed')!.textContent).toContain(expected);
        hover({ depth_val: 200 });
        expect(document.getElementById('depth-cursor-label')!.textContent).toBe(expected);
        expect(document.getElementById('depth-cursor-indicator')!.style.left).toBe('calc(100% - 1px)');
    });

    it('uses the selected unit for unsaturated readings and preserves actual negative readings', async () => {
        const { hover } = await initializeDepthLegend(100, 'm');
        hover({ depth_val: 40 });
        expect(document.getElementById('depth-cursor-label')!.textContent).toBe('12.2 m');
        expect(document.getElementById('depth-cursor-indicator')!.style.left).toBe('calc(40% - 1px)');
        hover({ depth_val: -10 });
        expect(document.getElementById('depth-cursor-label')!.textContent).toBe('-3.0 m');
        expect(document.getElementById('depth-cursor-indicator')!.style.left).toBe('calc(0% - 1px)');
    });

    it('never rounds a displayed reading above the custom maximum', async () => {
        const { hover } = await initializeDepthLegend(1.06);
        hover({ depth_val: 1.059 });
        expect(document.getElementById('depth-cursor-label')!.textContent).toBe('1.06 ft');
    });

    it('preserves the public default axis rounding and unbounded raw readings', async () => {
        const { hover } = await initializeDepthLegend(null, 'ft', 80.2);
        expect(document.getElementById('depth-scale-fixed')!.textContent).toContain('81 ft');
        hover({ depth_val: 90 });
        expect(document.getElementById('depth-cursor-label')!.textContent).toBe('90.0 ft');
        expect(document.getElementById('depth-cursor-indicator')!.style.left).toBe('calc(100% - 1px)');
    });

    it('refreshes a stationary cursor on limit, unit and reset without querying the map again', async () => {
        const { map, hover } = await initializeDepthLegend(100);
        hover({ depth_val: 80 });
        expect(document.getElementById('depth-cursor-label')!.textContent).toBe('80.0 ft');
        Layers.setDepthLimit(50, 'ft');
        await Layers.whenDisplayApplied();
        expect(document.getElementById('depth-cursor-label')!.textContent).toBe('50 ft');
        Layers.setDepthLimit(50, 'm');
        await Layers.whenDisplayApplied();
        expect(document.getElementById('depth-cursor-label')!.textContent).toBe('15.24 m');
        expect(document.getElementById('depth-cursor-label')!.style.display).toBe('block');
        Layers.setDepthLimit(null, 'ft');
        await Layers.whenDisplayApplied();
        expect(document.getElementById('depth-cursor-label')!.textContent).toBe('80.0 ft');
        expect(document.getElementById('depth-cursor-indicator')!.style.left).toBe('calc(40% - 1px)');
        expect(map.queryRenderedFeatures).toHaveBeenCalledTimes(1);
    });

    it('recovers legacy normalized readings from the cached project domain before clipping', async () => {
        const { hover } = await initializeDepthLegend(100);
        hover({ depth_norm: 0.75 });
        expect(document.getElementById('depth-cursor-label')!.textContent).toBe('100 ft');
        hover({ depth_norm: 0.25 });
        expect(document.getElementById('depth-cursor-label')!.textContent).toBe('50.0 ft');
        expect(document.getElementById('depth-cursor-indicator')!.style.left).toBe('calc(50% - 1px)');
    });

    it('keeps the legacy normalized fallback for a source without a project cache', async () => {
        const { hover } = await initializeDepthLegend(100);
        hover({ depth_norm: 0.25 }, 'unknown-source');
        expect(document.getElementById('depth-cursor-label')!.textContent).toBe('25.0 ft');
    });

    it.each([{ depth_val: null }, { depth_val: '' }, { depth_val: 'bad' }, {}])(
        'does not invent a cursor value for missing or invalid depth %s', async properties => {
            const { hover } = await initializeDepthLegend(100);
            hover(properties);
            expect(document.getElementById('depth-cursor-label')!.style.display).toBe('none');
        }
    );

    it('leaves unavailable depth N/A with a cap and recognizes measured zero depth', async () => {
        const { hover } = await initializeDepthLegend(100, 'm', null);
        expect(document.getElementById('depth-scale-fixed')!.textContent).toContain('N/A');
        hover({ depth_val: 40 });
        expect(document.getElementById('depth-cursor-label')!.style.display).toBe('none');
        State.projectDepthDomains.set('1', { min: 0, max: 0 });
        Layers.recomputeActiveDepthDomain();
        expect(document.getElementById('depth-scale-fixed')!.textContent).toContain('30.48 m');
        hover({ depth_val: 0 });
        expect(document.getElementById('depth-cursor-label')!.textContent).toBe('0.0 m');
    });

    it.each(['mouseout', 'colorMode', 'shotMode', 'visibility'])('clears cached hover on %s', async trigger => {
        const { hover, handlers } = await initializeDepthLegend(100);
        hover({ depth_val: 80 });
        if (trigger === 'mouseout') handlers.mouseout!();
        if (trigger === 'colorMode') await Layers.setColorMode('project');
        if (trigger === 'shotMode') await Layers.setColorMode('shot');
        if (trigger === 'visibility') await Layers.toggleProjectVisibility('1', false);
        expect(document.getElementById('depth-cursor-label')!.style.display).toBe('none');
        expect(DepthLegend.hoveredLineFeature).toBeNull();
        Layers.setDepthLimit(50, 'm');
        await Layers.whenDisplayApplied();
        expect(document.getElementById('depth-cursor-label')!.style.display).toBe('none');
    });

    it.each(['toggle', 'preference', 'removed'])('clears stale project hover after %s while another project keeps the domain', async change => {
        const { hover } = await initializeDepthLegend(100);
        Config._projects!.push({ id: '2' });
        State.projectDepthDomains.set('2', { min: 0, max: 400 });
        hover({ depth_val: 80 });
        if (change === 'toggle') await Layers.toggleProjectVisibility('1', false);
        if (change === 'preference') {
            State.projectLayerStates.set('1', false);
            Layers.recomputeActiveDepthDomain();
        }
        if (change === 'removed') {
            State.projectDepthDomains.delete('1');
            Layers.recomputeActiveDepthDomain();
        }
        expect(State.activeDepthDomain).toEqual({ min: 0, max: 100 });
        expect(document.getElementById('depth-cursor-label')!.style.display).toBe('none');
        expect(DepthLegend.hoveredLineFeature).toBeNull();
    });
});

it('ignores repeated initialization and retains display callbacks after teardown', () => {
    document.body.innerHTML = '<div id="map"></div>';
    const first = createMapMock();
    const second = createMapMock();
    DepthLegend.init(first.map);
    const pending = DepthLegend.onDisplayPendingHandler;
    const applied = DepthLegend.onDisplayAppliedHandler;
    DepthLegend.init(second.map);
    expect(second.map.on).not.toHaveBeenCalled();
    DepthLegend.destroy();
    expect(DepthLegend.map).toBeNull();
    expect(DepthLegend.onDisplayPendingHandler).toBe(pending);
    expect(DepthLegend.onDisplayAppliedHandler).toBe(applied);
    expect(first.map.off).toHaveBeenCalledTimes(2);
    expect(document.getElementById('depth-scale-fixed')!).not.toBeNull();
    document.body.innerHTML = '';
});
