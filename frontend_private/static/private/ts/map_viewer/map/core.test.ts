import type { Mock } from 'vitest';
import type { MapCoreMap } from '../../../../../../ts-types/domain/map-core.ts';
interface CoreMapFixture { addControl: Mock; on: Mock; resize: Mock; getLayer: Mock<() => boolean>; setLayoutProperty: Mock }
const mapSourcesMock = {
    getCurrentMapSourceId: vi.fn(),
    buildInitialMapStyle: vi.fn(),
    applyInitialMapSource: vi.fn(),
    installCheckedTileProtocol: vi.fn(),
    installCheckedTileFetch: vi.fn(),
    renderControl: vi.fn(),
};

vi.mock('./sources.ts', () => ({
    MapSources: mapSourcesMock,
}));

describe('MapCore', () => {
    let mapMock: CoreMapFixture;
    let mapConstructorSpy: Mock<() => CoreMapFixture>;
    let originalMapboxgl: typeof mapboxgl;

    beforeEach(() => {
        vi.useFakeTimers();
        vi.resetModules();
        vi.clearAllMocks();

        mapMock = {
            addControl: vi.fn(),
            on: vi.fn(),
            resize: vi.fn(),
            getLayer: vi.fn(() => false),
            setLayoutProperty: vi.fn(),
        };

        mapSourcesMock.getCurrentMapSourceId.mockReturnValue('esri-world-hillshade');
        mapSourcesMock.buildInitialMapStyle.mockReturnValue('mapbox://styles/mapbox/satellite-streets-v12');

        originalMapboxgl = globalThis.mapboxgl;
        mapConstructorSpy = vi.fn(function () {
            return mapMock;
        });
        vi.stubGlobal('mapboxgl', {
            accessToken: '',
            Map: mapConstructorSpy,
            NavigationControl: vi.fn(),
            FullscreenControl: vi.fn(),
            ScaleControl: vi.fn(),
        });
    });

    afterEach(() => {
        vi.useRealTimers();
        vi.restoreAllMocks();
        globalThis.mapboxgl = originalMapboxgl;
    });

    it('initializes the map with the safe initial map style', async () => {
        const { MapCore } = await import('./core.ts');

        const map = MapCore.init('token', 'map');

        expect(map).toBe(mapMock);
        expect(mapSourcesMock.installCheckedTileProtocol).toHaveBeenCalled();
        expect(mapSourcesMock.installCheckedTileFetch).toHaveBeenCalled();
        expect(mapSourcesMock.installCheckedTileProtocol.mock.invocationCallOrder[0]!)
            .toBeLessThan(mapConstructorSpy.mock.invocationCallOrder[0]!);
        expect(mapSourcesMock.getCurrentMapSourceId).toHaveBeenCalledWith('token');
        expect(mapSourcesMock.buildInitialMapStyle).toHaveBeenCalledWith('esri-world-hillshade', 'token');
        expect(mapConstructorSpy).toHaveBeenCalledWith(expect.objectContaining({
            container: 'map',
            style: 'mapbox://styles/mapbox/satellite-streets-v12',
        }));
    });

    it('delegates map source control rendering to the shared module', async () => {
        const { MapCore } = await import('./core.ts');

        MapCore.setupMapSourceControl(mapMock as unknown as MapCoreMap, 'token');

        expect(mapSourcesMock.renderControl).toHaveBeenCalledWith(mapMock, 'token');
    });

    it('includes the private toolbar and overlays in the fullscreen container', async () => {
        const { MapCore } = await import('./core.ts');
        const fullscreenContainer = document.createElement('section');

        MapCore.init('token', 'map', { fullscreenContainer });

        expect(mapboxgl.FullscreenControl).toHaveBeenCalledWith({ container: fullscreenContainer });
    });

});

describe('MapCore lifecycle callbacks', () => {
    it('resizes immediately through the timer and on resize, and clears only its own State map', async () => {
        vi.useFakeTimers();
        const { MapCore } = await import('./core.ts');
        const { State } = await import('../state.ts');
        const { Layers } = await import('./layers.ts');
        const { DEFAULTS } = await import('../config.ts');
        const handlers = new Map<string, () => void>();
        const map = { addControl: vi.fn(), on: vi.fn((name: string, callback: () => void) => handlers.set(name, callback)), resize: vi.fn(), getLayer: vi.fn(() => false) };
        vi.stubGlobal('mapboxgl', { Map: vi.fn(function () { return map; }), NavigationControl: vi.fn(), FullscreenControl: vi.fn(), ScaleControl: vi.fn() });
        const cancel = vi.spyOn(Layers, 'cancelPendingWork').mockImplementation(() => {});
        try {
            expect(MapCore.init('token')).toBe(map);
            expect(map.resize).not.toHaveBeenCalled();
            vi.advanceTimersByTime(DEFAULTS.MAP.RESIZE_DELAY_MS);
            expect(map.resize).toHaveBeenCalledOnce();
            window.dispatchEvent(new Event('resize'));
            expect(map.resize).toHaveBeenCalledTimes(2);
            handlers.get('load')!();
            expect(mapSourcesMock.applyInitialMapSource).toHaveBeenCalledWith(map, 'esri-world-hillshade', 'token');
            handlers.get('remove')!();
            expect(cancel).toHaveBeenCalledOnce();
            expect(State.map).toBeNull();
            handlers.get('remove')!();
            expect(cancel).toHaveBeenCalledOnce();
        } finally { cancel.mockRestore(); vi.unstubAllGlobals(); vi.useRealTimers(); }
    });
});
