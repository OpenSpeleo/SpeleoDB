const mapSourcesMock = {
    getCurrentMapSourceId: vi.fn(),
    buildInitialMapStyle: vi.fn(),
    applyInitialMapSource: vi.fn(),
    installCheckedTileProtocol: vi.fn(),
    installCheckedTileFetch: vi.fn(),
    renderControl: vi.fn(),
};

vi.mock('./sources.js', () => ({
    MapSources: mapSourcesMock,
}));

describe('MapCore', () => {
    let mapMock;
    let mapConstructorSpy;
    let originalMapboxgl;

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
        globalThis.mapboxgl = {
            accessToken: '',
            Map: mapConstructorSpy,
            NavigationControl: vi.fn(),
            FullscreenControl: vi.fn(),
            ScaleControl: vi.fn(),
        };
    });

    afterEach(() => {
        vi.useRealTimers();
        vi.restoreAllMocks();
        globalThis.mapboxgl = originalMapboxgl;
    });

    it('initializes the map with the safe initial map style', async () => {
        const { MapCore } = await import('./core.js');

        const map = MapCore.init('token', 'map');

        expect(map).toBe(mapMock);
        expect(mapSourcesMock.installCheckedTileProtocol).toHaveBeenCalled();
        expect(mapSourcesMock.installCheckedTileFetch).toHaveBeenCalled();
        expect(mapSourcesMock.installCheckedTileProtocol.mock.invocationCallOrder[0])
            .toBeLessThan(mapConstructorSpy.mock.invocationCallOrder[0]);
        expect(mapSourcesMock.getCurrentMapSourceId).toHaveBeenCalledWith('token');
        expect(mapSourcesMock.buildInitialMapStyle).toHaveBeenCalledWith('esri-world-hillshade', 'token');
        expect(mapConstructorSpy).toHaveBeenCalledWith(expect.objectContaining({
            container: 'map',
            style: 'mapbox://styles/mapbox/satellite-streets-v12',
        }));
    });

    it('delegates map source control rendering to the shared module', async () => {
        const { MapCore } = await import('./core.js');

        MapCore.setupMapSourceControl(mapMock, 'token');

        expect(mapSourcesMock.renderControl).toHaveBeenCalledWith(mapMock, 'token');
    });

});
