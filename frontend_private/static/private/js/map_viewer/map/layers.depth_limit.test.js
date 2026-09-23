import { Config } from '../config.js';
import { ProjectPanel } from '../components/project_panel.js';
import { State, createDefaultDisplayPreferences } from '../state.js';
import { Colors } from './colors.js';
import { Geometry } from './geometry.js';
import { Layers } from './layers.js';
import { flushPreferenceWrites } from '../display_preference_storage.js';

function createMapMock() {
    const sources = new Map();
    const layerDefinitions = new Map();
    const map = {
        getStyle: vi.fn(() => ({})),
        getSource: vi.fn(id => sources.get(id)),
        addSource: vi.fn((id, source) => sources.set(id, { ...source, setData: vi.fn() })),
        getLayer: vi.fn(id => layerDefinitions.get(id)),
        addLayer: vi.fn(layer => layerDefinitions.set(layer.id, layer)),
        setPaintProperty: vi.fn(),
        setLayoutProperty: vi.fn(),
        setFilter: vi.fn(),
    };
    return { map, sources, layerDefinitions };
}

describe('Layers custom depth maximum', () => {
    beforeEach(() => {
        flushPreferenceWrites();
        localStorage.clear();
        ProjectPanel._countryVisibility = null;
        State.resetLayerState();
        State.displayPreferences = createDefaultDisplayPreferences();
        State.map = null;
        Config._projects = [{ id: '1', color: '#ff0000' }, { id: '2', color: '#00ff00' }];
        State.projectDepthDomains.set('1', Object.freeze({ min: 0, max: 25 }));
        State.projectDepthDomains.set('2', Object.freeze({ min: 0, max: 200 }));
        vi.spyOn(Geometry, 'cachePreparedSnapPoints').mockImplementation(() => {});
    });

    afterEach(() => {
        vi.restoreAllMocks();
        vi.unstubAllGlobals();
        State.map = null;
    });

    it('fixes the scale for shallow and deep visible projects without changing cached domains', async () => {
        expect(Layers.setDepthLimit(100, 'ft')).toBe(true);
        await Layers.whenDisplayApplied();
        expect(State.activeDepthDomain).toEqual({ min: 0, max: 100 });
        await Layers.toggleProjectVisibility('2', false);
        expect(State.activeDepthDomain).toEqual({ min: 0, max: 100 });
        expect(State.projectDepthDomains.get('1')).toEqual({ min: 0, max: 25 });
        expect(State.projectDepthDomains.get('2')).toEqual({ min: 0, max: 200 });
        await Layers.toggleProjectVisibility('1', false);
        expect(State.activeDepthDomain).toBeNull();
        await Layers.toggleProjectVisibility('2', true);
        expect(State.activeDepthDomain).toEqual({ min: 0, max: 100 });
    });

    it('respects country gates independently of saved individual preferences', async () => {
        State.projectLayerStates.set('1', true);
        State.projectLayerStates.set('2', true);
        State.effectiveProjectVisibility.set('1', false);
        State.effectiveProjectVisibility.set('2', false);
        Layers.setDepthLimit(100, 'm');
        await Layers.whenDisplayApplied();
        expect(State.activeDepthDomain).toBeNull();
        State.effectiveProjectVisibility.set('1', true);
        Layers.recomputeActiveDepthDomain();
        expect(State.activeDepthDomain).toEqual({ min: 0, max: 100 });
        expect(Layers.getVisibleProjectIds()).toEqual(['1']);
    });

    it.each([
        { limitFeet: 100, otherCountryVisible: false },
        { limitFeet: 100, otherCountryVisible: true },
        { limitFeet: null, otherCountryVisible: false },
        { limitFeet: null, otherCountryVisible: true },
    ])('keeps actual panel toggles inside a hidden country out of the depth domain: %j', async ({ limitFeet, otherCountryVisible }) => {
        localStorage.clear();
        document.body.innerHTML = '<div id="map"></div>';
        Config._projects = [
            { id: '1', name: 'Shallow cave', country: 'US', color: '#ff0000' },
            { id: '2', name: 'Deep cave', country: 'MX', color: '#00ff00' },
        ];
        const { map, layerDefinitions } = createMapMock();
        State.map = map;
        for (const project of Config.projects) {
            const layerId = `project-layer-${project.id}`;
            layerDefinitions.set(layerId, { type: 'line' });
            State.allProjectLayers.set(project.id, [layerId]);
        }
        const domains = [];
        const onDomainChanged = event => domains.push(event.detail.domain);
        window.addEventListener('speleo:depth-domain-updated', onDomainChanged);

        try {
            ProjectPanel.render();
            Layers.setDepthLimit(limitFeet, 'ft');
            await Layers.whenDisplayApplied();
            await Layers.setColorMode('depth');
            if (!otherCountryVisible) document.querySelector('[data-country="US"] .country-toggle').click();
            await Layers.whenDisplayApplied();
            document.querySelector('[data-country="MX"] .country-toggle').click();
            await Layers.whenDisplayApplied();
            const expectedDomain = otherCountryVisible ? { min: 0, max: limitFeet ?? 25 } : null;
            expect(State.activeDepthDomain).toEqual(expectedDomain);
            domains.length = 0;
            map.setPaintProperty.mockClear();

            // Change the individual preference OFF and ON while its country stays hidden.
            document.querySelector('[data-project-id="2"] input').click();
            await Layers.whenDisplayApplied();
            document.querySelector('[data-project-id="2"] input').click();
            await Layers.whenDisplayApplied();

            expect(Layers.isProjectVisible('2')).toBe(true);
            expect(Layers.isProjectEffectivelyVisible('2')).toBe(false);
            expect(State.activeDepthDomain).toEqual(expectedDomain);
            expect(domains).toEqual([expectedDomain, expectedDomain]);
            // Both line layers repaint exactly once per toggle, with no transient range.
            expect(map.setPaintProperty.mock.calls).toEqual([
                ['project-layer-1', 'line-color', Colors.getDepthPaint(expectedDomain)],
                ['project-layer-2', 'line-color', Colors.getDepthPaint(expectedDomain)],
                ['project-layer-1', 'line-color', Colors.getDepthPaint(expectedDomain)],
                ['project-layer-2', 'line-color', Colors.getDepthPaint(expectedDomain)],
            ]);

            Layers.setDepthLimit(null, 'ft');

            await Layers.whenDisplayApplied();
            expect(State.activeDepthDomain).toEqual(otherCountryVisible ? { min: 0, max: 25 } : null);
            Layers.setDepthLimit(limitFeet, 'ft');
            await Layers.whenDisplayApplied();
            document.querySelector('[data-country="MX"] .country-toggle').click();
            await Layers.whenDisplayApplied();
            expect(Layers.isProjectEffectivelyVisible('2')).toBe(true);
            expect(State.activeDepthDomain).toEqual({ min: 0, max: limitFeet ?? 200 });

            document.querySelector('[data-country="MX"] .country-toggle').click();

            await Layers.whenDisplayApplied();
            document.querySelector('[data-project-id="2"] input').click();
            await Layers.whenDisplayApplied();
            document.querySelector('[data-country="MX"] .country-toggle').click();
            await Layers.whenDisplayApplied();
            expect(Layers.isProjectVisible('2')).toBe(false);
            expect(Layers.isProjectEffectivelyVisible('2')).toBe(false);
            expect(State.activeDepthDomain).toEqual(expectedDomain);
        } finally {
            window.removeEventListener('speleo:depth-domain-updated', onDomainChanged);
            document.body.innerHTML = '';
            localStorage.clear();
        }
    });

    it('preserves unavailable and zero-depth meanings', async () => {
        State.projectDepthDomains.set('1', null);
        State.projectDepthDomains.set('2', null);
        Layers.setDepthLimit(100, 'ft');
        await Layers.whenDisplayApplied();
        expect(State.activeDepthDomain).toBeNull();
        State.projectDepthDomains.set('1', { min: 0, max: 0 });
        Layers.recomputeActiveDepthDomain();
        expect(State.activeDepthDomain).toEqual({ min: 0, max: 100 });
        Layers.setDepthLimit(null, 'ft');
        await Layers.whenDisplayApplied();
        expect(State.activeDepthDomain).toEqual({ min: 0, max: 0 });
    });

    it('updates preferences and the legend event once without repainting survey colors', async () => {
        const repaint = vi.spyOn(Layers, 'applyDepthLineColors');
        const domainEvent = vi.fn();
        const preferencesEvent = vi.fn();
        window.addEventListener('speleo:depth-domain-updated', domainEvent);
        window.addEventListener('speleo:display-preferences-changed', preferencesEvent);
        try {
            Layers.setDepthLimit(100, 'ft');
            await Layers.whenDisplayApplied();
            expect(repaint).not.toHaveBeenCalled();
            expect(domainEvent).toHaveBeenCalledTimes(1);
            expect(preferencesEvent).toHaveBeenCalledTimes(1);
            expect(State.displayPreferences.depthLimitFeet).toBe(100);
            expect(Layers.setDepthLimit(100, 'ft')).toBe(true);
            await Layers.whenDisplayApplied();
            expect(domainEvent).toHaveBeenCalledTimes(1);
            expect(preferencesEvent).toHaveBeenCalledTimes(1);
            Layers.setDepthLimit(100, 'm');
            await Layers.whenDisplayApplied();
            expect(domainEvent).toHaveBeenCalledTimes(2);
            expect(preferencesEvent).toHaveBeenCalledTimes(2);
            expect(State.activeDepthDomain).toEqual({ min: 0, max: 100 });
        } finally {
            window.removeEventListener('speleo:depth-domain-updated', domainEvent);
            window.removeEventListener('speleo:display-preferences-changed', preferencesEvent);
        }
    });

    it.each([[0, 'ft'], [-1, 'ft'], [NaN, 'm'], [Infinity, 'ft'], ['50', 'ft'], [50, 'yd']])(
        'rejects invalid input %s %s without touching the previous setting', async (value, unit) => {
            Layers.setDepthLimit(100, 'ft');
            await Layers.whenDisplayApplied();
            const emit = vi.spyOn(Layers, 'emitDisplayPreferencesChanged');
            expect(Layers.setDepthLimit(value, unit)).toBe(false);
            await Layers.whenDisplayApplied();
            expect(State.displayPreferences.depthLimitFeet).toBe(100);
            expect(State.displayPreferences.depthUnit).toBe('ft');
            expect(emit).not.toHaveBeenCalled();
        }
    );

    it('repaints only the effective scale and never reads raw sources during controls or visibility changes', async () => {
        const { map, layerDefinitions } = createMapMock();
        State.map = map;
        layerDefinitions.set('project-layer-1', { type: 'line' });
        State.allProjectLayers.set('1', ['project-layer-1']);
        await Layers.setColorMode('depth');
        map.setPaintProperty.mockClear();
        Layers.setDepthLimit(50, 'ft');
        await Layers.whenDisplayApplied();
        expect(map.setPaintProperty).toHaveBeenLastCalledWith(
            'project-layer-1', 'line-color', Colors.getDepthPaint({ min: 0, max: 50 })
        );
        map.setPaintProperty.mockClear();
        Layers.setDepthLimit(50, 'm');
        await Layers.whenDisplayApplied();
        expect(map.setPaintProperty).not.toHaveBeenCalled();
        await Layers.toggleProjectVisibility('2', false);
        await Layers.setColorMode('project');
        Layers.setDepthLimit(250, 'ft');
        await Layers.whenDisplayApplied();
        await Layers.setColorMode('depth');
        expect(State.activeDepthDomain).toEqual({ min: 0, max: 250 });
        expect(map.getSource).not.toHaveBeenCalled();
        expect(Geometry.cachePreparedSnapPoints).not.toHaveBeenCalled();
    });

    it('reset restores the automatic domain even while survey colors are active', async () => {
        Layers.setDepthLimit(50, 'm');
        await Layers.whenDisplayApplied();
        State.displayPreferences = createDefaultDisplayPreferences();
        await Layers.applyDisplayPreferences();
        expect(State.activeDepthDomain).toEqual({ min: 0, max: 200 });
        expect(State.displayPreferences.depthLimitFeet).toBeNull();
        expect(State.displayPreferences.depthUnit).toBe('ft');
    });

    it('applies a limit chosen before GeoJSON arrives while preserving loaded raw depth', async () => {
        const { map, sources } = createMapMock();
        State.map = map;
        State.projectDepthDomains.clear();
        vi.stubGlobal('mapboxgl', {
            LngLatBounds: class { extend() { return this; } isEmpty() { return true; } },
        });
        let deliver;
        vi.stubGlobal('fetch', vi.fn(() => new Promise(resolve => { deliver = resolve; })));
        const pending = Layers.addProjectGeoJSON('1', '/survey.geojson');
        Layers.setDepthLimit(50, 'ft');
        await Layers.whenDisplayApplied();
        await Layers.setColorMode('depth');
        expect(State.activeDepthDomain).toBeNull();
        deliver({ ok: true, json: async () => ({
            type: 'FeatureCollection',
            features: [{ type: 'Feature', properties: { depth: 200 }, geometry: {
                type: 'LineString', coordinates: [[-87, 20], [-88, 21]],
            } }],
        }) });
        await pending;
        expect(State.projectDepthDomains.get('1')).toEqual({ min: 0, max: 200 });
        expect(State.activeDepthDomain).toEqual({ min: 0, max: 50 });
        const rawProperties = sources.get('project-geojson-1').data.features[0].properties;
        expect(rawProperties.depth_val).toBe(200);
        expect(rawProperties.depth_norm).toBe(1);
        Layers.setDepthLimit(null, 'ft');
        await Layers.whenDisplayApplied();
        expect(State.activeDepthDomain).toEqual({ min: 0, max: 200 });
        expect(rawProperties.depth_val).toBe(200);
    });
});
