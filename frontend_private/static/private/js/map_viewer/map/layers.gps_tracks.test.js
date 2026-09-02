const mocks = vi.hoisted(() => ({
    getGPSTrackDetails: vi.fn(),
}));

vi.mock('../api.js', () => ({
    API: { getGPSTrackDetails: mocks.getGPSTrackDetails },
}));

vi.mock('../config.js', () => ({
    Config: {},
    DEFAULTS: { ZOOM_LEVELS: {} },
}));

vi.mock('../state.js', () => ({
    State: {
        gpsTrackLayerStates: new Map(),
        gpsTrackLoadingStates: new Map(),
        gpsTrackCache: new Map(),
    },
}));

vi.mock('./colors.js', () => ({ Colors: {} }));
vi.mock('./geometry.js', () => ({ Geometry: {} }));

import { State } from '../state.js';
import { Layers } from './layers.js';

describe('GPS Track lazy loading', () => {
    beforeEach(() => {
        State.gpsTrackLayerStates.clear();
        State.gpsTrackLoadingStates.clear();
        State.gpsTrackCache.clear();
        mocks.getGPSTrackDetails.mockReset();
        vi.restoreAllMocks();
    });

    it('authorizes a fresh signed URL immediately before the first download', async () => {
        mocks.getGPSTrackDetails.mockResolvedValue({ file: '/fresh-signed-url' });
        globalThis.fetch = vi.fn().mockResolvedValue({
            ok: true,
            json: vi.fn().mockResolvedValue({
                type: 'FeatureCollection',
                features: [],
            }),
        });
        vi.spyOn(Layers, 'addGPSTrackLayer').mockResolvedValue();

        await Layers.toggleGPSTrackVisibility('track-1', true);

        expect(mocks.getGPSTrackDetails).toHaveBeenCalledWith('track-1');
        expect(fetch).toHaveBeenCalledWith('/fresh-signed-url');
        expect(State.gpsTrackCache.has('track-1')).toBe(true);
    });

    it('never fetches an undefined URL when detail metadata has no file', async () => {
        mocks.getGPSTrackDetails.mockResolvedValue({ id: 'track-1' });
        globalThis.fetch = vi.fn();

        await Layers.toggleGPSTrackVisibility('track-1', true);

        expect(fetch).not.toHaveBeenCalled();
        expect(State.gpsTrackLayerStates.get('track-1')).toBe(false);
        expect(State.gpsTrackLoadingStates.get('track-1')).toBe(false);
        expect(State.gpsTrackCache.has('track-1')).toBe(false);
    });
});
