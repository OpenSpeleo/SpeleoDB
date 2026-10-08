import { rememberSourceData } from './layers/source_lifecycle.ts';
import type { ViewerMap } from '../../../../../../ts-types/domain/map-state.ts';
import type { RendererImage, MapPointCollection } from '../../../../../../ts-types/domain/renderer.ts';
import { Layers } from './layers.ts';
import { State } from '../state.ts';
import { configureRuntimeContext } from '../runtime_context.ts';

beforeEach(() => { State.resetLayerState(); });
afterEach(() => { State.resetLayerState(); State.map = null; vi.restoreAllMocks(); });

function stationSource() {
    const data: MapPointCollection = { type: 'FeatureCollection', features: [{
        type: 'Feature', id: 'station', properties: { name: 'Before', color: '#ffffff' },
        geometry: { type: 'Point', coordinates: [1, 2] },
    }] };
    const source = { setData: vi.fn((_data: MapPointCollection) => {}) };
    rememberSourceData(source, data);
    State.map = { getSource: () => source } as unknown as ViewerMap;
    return { data, source, feature: data.features[0]! };
}

it.each(['subsurface', 'surface'] as const)('mutates the existing %s source and station record without replacing either', (kind) => {
    const { data, source, feature } = stationSource();
    const record = { id: 'station', name: 'Before', latitude: 2, longitude: 1 };
    const records = kind === 'surface' ? State.allSurfaceStations : State.allStations;
    records.set('station', record);
    const position = kind === 'surface' ? Layers.updateSurfaceStationPosition : Layers.updateStationPosition;
    const color = kind === 'surface' ? Layers.updateSurfaceStationColor : Layers.updateStationColor;
    const properties = kind === 'surface' ? Layers.updateSurfaceStationProperties : Layers.updateStationProperties;
    const coords: [number, number] = [3, 4];
    position('scope', 'station', coords);
    color('scope', 'station', '#123456');
    properties('scope', 'station', { name: 'After' });
    expect(feature.geometry.coordinates).toBe(coords);
    expect(feature.properties).toEqual({ name: 'After', color: '#123456' });
    expect(records.get('station')).toBe(record);
    expect(record).toMatchObject({ longitude: 3, latitude: 4 });
    expect(source.setData).toHaveBeenCalledTimes(3);
    for (const [argument] of source.setData.mock.calls) expect(argument).toBe(data);
});

it('leaves missing station features unchanged and restores landmark coordinate identity', () => {
    const { data, source, feature } = stationSource();
    Layers.updateStationPosition('scope', 'absent', [5, 6]);
    expect(source.setData).not.toHaveBeenCalled();
    const record = { id: 'station', name: 'Place', latitude: 2, longitude: 1 };
    State.allLandmarks.set('station', record);
    const coords: [number, number] = [8, 9];
    Layers.revertLandmarkPosition('station', coords);
    expect(feature.geometry.coordinates).toBe(coords);
    expect(State.allLandmarks.get('station')).toBe(record);
    expect(record).toMatchObject({ longitude: 8, latitude: 9 });
    expect(source.setData).toHaveBeenCalledWith(data);
});

it('publishes station refresh synchronously on Window and returns a promise', async () => {
    const events: Event[] = [];
    const onEvent = (event: Event) => events.push(event);
    window.addEventListener('speleo:refresh-stations', onEvent);
    window.addEventListener('speleo:refresh-surface-stations', onEvent);
    try {
        const station = Layers.refreshStationsAfterChange(3);
        const surface = Layers.refreshSurfaceStationsAfterChange('network');
        expect(events.map(event => [event.type, (event as CustomEvent<{ projectId?: string | number; networkId?: string | number }>).detail])).toEqual([
            ['speleo:refresh-stations', { projectId: 3 }],
            ['speleo:refresh-surface-stations', { networkId: 'network' }],
        ]);
        expect(station).toBeInstanceOf(Promise);
        expect(surface).toBeInstanceOf(Promise);
        await Promise.all([station, surface]);
    } finally {
        window.removeEventListener('speleo:refresh-stations', onEvent);
        window.removeEventListener('speleo:refresh-surface-stations', onEvent);
    }
});

it('loads images sequentially, skips existing images and retries a missing image on a later map', async () => {
    configureRuntimeContext({ icons: { cylinderOrange: '/cylinder', explorationLead: '/lead', biology: '/biology', bone: '/bone', artifact: '/artifact', geology: '/geology' } });
    const images = new Set<string>();
    const image = {} as RendererImage;
    const loadImage = vi.fn(async (_url: string) => ({ data: image }));
    const addImage = vi.fn((id: string) => { images.add(id); });
    State.map = { hasImage: (id: string) => images.has(id), loadImage, addImage } as unknown as ViewerMap;
    await Layers.loadMarkerImages();
    expect(loadImage.mock.calls.map(([url]) => url)).toEqual(['/cylinder', '/lead', '/biology', '/bone', '/artifact', '/geology']);
    await Layers.loadMarkerImages();
    expect(loadImage).toHaveBeenCalledTimes(6);
    images.delete('bone-station-icon');
    await Layers.loadMarkerImages();
    expect(loadImage.mock.calls[6]?.[0]).toBe('/bone');
    expect(addImage).toHaveBeenCalledTimes(7);
});

it('catches image failures and resumes with only missing icons on retry', async () => {
    const images = new Set<string>();
    const image = {} as RendererImage;
    let fail = true;
    const log = vi.spyOn(console, 'error').mockImplementation(() => {});
    const loadImage = vi.fn(async (_url: string) => {
        if (fail) throw new Error('image failed');
        return { data: image };
    });
    State.map = { hasImage: (id: string) => images.has(id), loadImage, addImage: (id: string) => images.add(id) } as unknown as ViewerMap;
    await expect(Layers.loadMarkerImages()).resolves.toBeUndefined();
    expect(loadImage).toHaveBeenCalledOnce();
    expect(log).toHaveBeenCalledOnce();
    fail = false;
    await Layers.loadMarkerImages();
    expect(images.size).toBe(6);
});
