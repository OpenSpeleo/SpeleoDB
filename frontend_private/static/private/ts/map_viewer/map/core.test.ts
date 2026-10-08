import { attachGlobeAtmosphere } from '@speleodb/map-viewer';
import type { Mock } from 'vitest';
import type { MapCoreMap } from '../../../../../../ts-types/domain/map-core.ts';
interface CoreMapFixture { addControl: Mock; on: Mock; resize: Mock; jumpTo: Mock; getLayer: Mock<() => boolean>; setLayoutProperty: Mock; setStyle: Mock }
vi.mock('@speleodb/map-viewer', async (importOriginal) => ({
    ...await importOriginal<typeof import('@speleodb/map-viewer')>(),
    attachGlobeAtmosphere: vi.fn(),
}));

const mapSourcesMock = {
    getCurrentMapSourceId: vi.fn(),
    buildInitialMapStyle: vi.fn(),
    applyInitialMapSource: vi.fn(),
    installCheckedTileProtocol: vi.fn(),
    renderControl: vi.fn(),
};

vi.mock('./sources.ts', () => ({
    MapSources: mapSourcesMock,
}));

describe('MapCore', () => {
    let mapMock: CoreMapFixture;
    let mapConstructorSpy: Mock<() => CoreMapFixture>;
    let originalRenderergl: typeof __mapRenderer;

    beforeEach(() => {
        vi.useFakeTimers();
        vi.resetModules();
        vi.clearAllMocks();

        mapMock = {
            addControl: vi.fn(),
            on: vi.fn(),
            resize: vi.fn(),
            jumpTo: vi.fn(),
            getLayer: vi.fn(() => false),
            setLayoutProperty: vi.fn(),
            setStyle: vi.fn(),
        };

        mapSourcesMock.getCurrentMapSourceId.mockReturnValue('esri-world-hillshade');
        mapSourcesMock.buildInitialMapStyle.mockReturnValue('mapbox://styles/mapbox/satellite-streets-v12');

        originalRenderergl = globalThis.__mapRenderer;
        mapConstructorSpy = vi.fn(function () {
            return mapMock;
        });
        vi.stubGlobal('__mapRenderer', {
            accessToken: '',
            Map: mapConstructorSpy,
            AttributionControl: vi.fn(),
            NavigationControl: vi.fn(),
            FullscreenControl: vi.fn(),
            ScaleControl: vi.fn(),
        });
    });

    afterEach(() => {
        vi.useRealTimers();
        vi.restoreAllMocks();
        globalThis.__mapRenderer = originalRenderergl;
    });

    it('initializes the map with the safe initial map style', async () => {
        const { MapCore } = await import('./core.ts');

        const map = MapCore.init('token', 'map');

        expect(map).toBe(mapMock);
        expect(attachGlobeAtmosphere).toHaveBeenCalledExactlyOnceWith(mapMock);
        expect(vi.mocked(attachGlobeAtmosphere).mock.invocationCallOrder[0]!)
            .toBeLessThan(mapMock.setStyle.mock.invocationCallOrder[0]!);
        expect(mapSourcesMock.installCheckedTileProtocol).toHaveBeenCalled();
        expect(mapSourcesMock.installCheckedTileProtocol.mock.invocationCallOrder[0]!)
            .toBeLessThan(mapConstructorSpy.mock.invocationCallOrder[0]!);
        expect(mapSourcesMock.getCurrentMapSourceId).toHaveBeenCalledWith('token');
        expect(mapSourcesMock.buildInitialMapStyle).toHaveBeenCalledWith('esri-world-hillshade', 'token');
        expect(mapConstructorSpy).toHaveBeenCalledWith(expect.objectContaining({
            container: 'map',
            style: null,
            attributionControl: false,
        }));
        expect(__mapRenderer.AttributionControl).toHaveBeenCalledExactlyOnceWith();
        expect(mapMock.addControl).toHaveBeenNthCalledWith(1, {
            onAdd: expect.any(Function) as unknown,
            onRemove: expect.any(Function) as unknown,
        }, 'bottom-right');
        expect(mapMock.setStyle).toHaveBeenCalledWith('mapbox://styles/mapbox/satellite-streets-v12', { transformStyle: expect.any(Function) as unknown });
    });

    it('delegates map source control rendering to the shared module', async () => {
        const { MapCore } = await import('./core.ts');

        MapCore.setupMapSourceControl(mapMock as unknown as MapCoreMap, 'token');

        expect(mapSourcesMock.renderControl).toHaveBeenCalledWith(mapMock, 'token');
    });

    it('restores the wide France camera after the first globe style, without resetting later navigation', async () => {
        const { MapCore } = await import('./core.ts');
        const handlers = new Map<string, () => void>();
        mapMock.on.mockImplementation((event: string, callback: () => void) => handlers.set(event, callback));

        MapCore.init('token');
        expect(mapMock.jumpTo).not.toHaveBeenCalled();
        handlers.get('style.load')!();
        expect(mapMock.jumpTo).toHaveBeenCalledExactlyOnceWith({ center: [2.35, 46.6], zoom: 0 });

        handlers.get('style.load')!();
        expect(mapMock.jumpTo).toHaveBeenCalledTimes(1);
    });

    it('includes the private toolbar and overlays in the fullscreen container', async () => {
        const { MapCore } = await import('./core.ts');
        const fullscreenContainer = document.createElement('section');

        MapCore.init('token', 'map', { fullscreenContainer });

        expect(__mapRenderer.FullscreenControl).toHaveBeenCalledWith({ container: fullscreenContainer });
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
        const map = { addControl: vi.fn(), on: vi.fn((name: string, callback: () => void) => handlers.set(name, callback)), resize: vi.fn(), setStyle: vi.fn(), getLayer: vi.fn(() => false) };
        vi.stubGlobal('__mapRenderer', { Map: vi.fn(function () { return map; }), AttributionControl: vi.fn(), NavigationControl: vi.fn(), FullscreenControl: vi.fn(), ScaleControl: vi.fn() });
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
            window.dispatchEvent(new Event('resize'));
            vi.runAllTimers();
            expect(map.resize).toHaveBeenCalledTimes(2);
            handlers.get('remove')!();
            expect(cancel).toHaveBeenCalledOnce();
        } finally { cancel.mockRestore(); vi.unstubAllGlobals(); vi.useRealTimers(); }
    });
});
