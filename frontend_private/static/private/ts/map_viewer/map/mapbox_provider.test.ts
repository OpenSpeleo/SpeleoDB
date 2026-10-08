import type { MapCoreMap } from '../../../../../../ts-types/domain/map-core.ts';
import { normalizeMapboxRequest, normalizeProviderStyle, createMapboxAttributionControl, withoutMapboxFeedback } from './mapbox_provider.ts';

it.each([
    ['mapbox://styles/mapbox/satellite-streets-v12', '/styles/v1/mapbox/satellite-streets-v12'],
    ['mapbox://mapbox.mapbox-streets-v8,mapbox.mapbox-terrain-v2', '/v4/mapbox.mapbox-streets-v8,mapbox.mapbox-terrain-v2.json'],
    ['mapbox://fonts/mapbox/Open Sans Regular/0-255.pbf', '/fonts/v1/mapbox/Open%20Sans%20Regular/0-255.pbf'],
    ['mapbox://sprites/mapbox/satellite-streets-v12.json', '/styles/v1/mapbox/satellite-streets-v12/sprite.json'],
    ['mapbox://sprites/mapbox/satellite-streets-v12@2x.png', '/styles/v1/mapbox/satellite-streets-v12/sprite@2x.png'],
])('normalizes classic provider resource %s without changing its identity', (resource, path) => {
    const normalized = new URL(normalizeMapboxRequest(resource, 'public+token').url);
    expect(normalized.origin).toBe('https://api.mapbox.com');
    expect(normalized.pathname).toBe(path);
    expect(normalized.searchParams.get('access_token')).toBe('public+token');
});

it('requests secure TileJSON and preserves provider query parameters', () => {
    const result = new URL(normalizeMapboxRequest('mapbox://mapbox.satellite?fresh=true', 'token').url);
    expect(result.searchParams.get('secure')).toBe('true');
    expect(result.searchParams.get('fresh')).toBe('true');
});

it.each([
    'https://example.com/survey.geojson',
    'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/1/2/3',
    'https://api.mapbox.com/v4/mapbox.satellite/1/2/3.jpg?access_token=provider-token',
    'speleo-checked-tile://https/server.arcgisonline.com/tile/1/2/3',
])('never attaches provider credentials to unrelated or already resolved URL %s', url => {
    expect(normalizeMapboxRequest(url, 'secret')).toEqual({ url });
});

it('translates provider projection while retaining the original source and vector label definitions', () => {
    const style = { version: 8, sources: {}, layers: [
        { id: 'settlement-major-label', source: 'composite', type: 'symbol', layout: { 'text-field': ['get', 'name'] } },
    ], projection: { name: 'globe' } };
    const normalized = normalizeProviderStyle(undefined, style as unknown as import('maplibre-gl').StyleSpecification);
    expect(normalized.projection).toEqual({ type: 'globe' });
    expect(normalized.layers).toBe(style.layers);
    expect(normalized.sources).toBe(style.sources);
    expect(style.projection).toEqual({ name: 'globe' });
});

it('retains accessible provider artwork and removes its control cleanly', () => {
    const control = createMapboxAttributionControl();
    const element = control.onAdd();
    document.body.appendChild(element);
    expect(element.querySelector('a')?.href).toBe('https://www.mapbox.com/about/maps/');
    expect(element.querySelector('img')?.alt).toBe('Mapbox');
    expect(element.querySelector('img')?.getAttribute('src')).toBe(new URL('../../../media/mapbox-provider-logo.svg', import.meta.url).href);
    control.onRemove();
    expect(element.isConnected).toBe(false);
});

it('removes the provider camera without changing the downloaded style', () => {
    const style: import('maplibre-gl').StyleSpecification = {
        version: 8, sources: {}, layers: [],
        center: [55.13, 25.12], zoom: 12, bearing: 30, pitch: 45, roll: 10,
    };
    const normalized = normalizeProviderStyle(undefined, style);
    for (const key of ['center', 'zoom', 'bearing', 'pitch', 'roll'] as const) {
        expect(normalized).not.toHaveProperty(key);
        expect(style).toHaveProperty(key);
    }
});

describe('native attribution feedback filtering', () => {
    function fixture() {
        const container = document.createElement('details');
        container.innerHTML = '<summary>Toggle attribution</summary><div>'
            + '<a href="https://www.mapbox.com/about/maps/">© Mapbox</a> | '
            + '<a href="https://www.openstreetmap.org/copyright">© OpenStreetMap</a> | '
            + '<span>Esri</span> | '
            + '<a class="mapbox-improve-map" href="https://www.mapbox.com/contribute/">Improve this map</a>'
            + '</div>';
        const native = {
            onAdd: vi.fn((_map: MapCoreMap) => container),
            onRemove: vi.fn(() => container.remove()),
        };
        const control = withoutMapboxFeedback(native);
        const map = {} as MapCoreMap;
        return { container, native, control, map };
    }

    it('removes only the matching feedback anchor inside its control and retains native credits and toggle', () => {
        const { container, native, control, map } = fixture();
        const toggle = container.querySelector('summary');
        const outside = container.cloneNode(true) as HTMLElement;
        document.body.append(outside);
        const unrelated = document.createElement('a');
        unrelated.className = 'mapbox-improve-map';
        unrelated.href = 'https://example.com/contribute/';
        container.append(unrelated);
        try {
            expect(control.onAdd(map)).toBe(container);
            expect(native.onAdd).toHaveBeenCalledExactlyOnceWith(map);
            expect(native.onAdd.mock.contexts[0]).toBe(native);
            expect(container.querySelector('a[href="https://www.mapbox.com/contribute/"]')).toBeNull();
            expect(container.querySelector('summary')).toBe(toggle);
            expect(container.querySelector('a[href="https://www.mapbox.com/about/maps/"]')?.textContent).toBe('© Mapbox');
            expect(container.querySelector('a[href="https://www.openstreetmap.org/copyright"]')?.textContent).toBe('© OpenStreetMap');
            expect(container.textContent).toContain('Esri');
            expect(unrelated.parentElement).toBe(container);
            expect(outside.querySelector('.mapbox-improve-map')).not.toBeNull();
        } finally {
            control.onRemove();
            outside.remove();
        }
    });

    it('filters updated native attribution contents when the active source changes', async () => {
        const { container, control, map } = fixture();
        control.onAdd(map);
        try {
            container.querySelector('div')!.innerHTML = '<span>Updated provider credits</span>'
                + '<a class="mapbox-improve-map" href="https://www.mapbox.com/contribute/">Improve this map</a>';
            await vi.waitFor(() => expect(container.querySelector('.mapbox-improve-map')).toBeNull());
            expect(container.textContent).toContain('Updated provider credits');
            expect(container.querySelector('summary')?.textContent).toBe('Toggle attribution');
        } finally {
            control.onRemove();
        }
    });

    it('disconnects before delegating native removal without changing its method binding', async () => {
        const { container, native, control, map } = fixture();
        document.body.append(control.onAdd(map));
        native.onRemove.mockImplementation(() => {
            const feedback = document.createElement('a');
            feedback.className = 'mapbox-improve-map';
            feedback.href = 'https://www.mapbox.com/contribute/';
            container.append(feedback);
            container.remove();
        });
        control.onRemove();
        await Promise.resolve();
        expect(native.onRemove).toHaveBeenCalledExactlyOnceWith();
        expect(native.onRemove.mock.contexts[0]).toBe(native);
        expect(container.isConnected).toBe(false);
        expect(container.querySelector('.mapbox-improve-map')).not.toBeNull();
    });
});
