const mocks = vi.hoisted(() => ({
    getGPSTrackDetails: vi.fn(),
}));

vi.mock('../api.js', () => ({
    API: { getGPSTrackDetails: mocks.getGPSTrackDetails },
}));

vi.mock('./colors.js', () => ({ Colors: {} }));
vi.mock('./geometry.js', () => ({ Geometry: {} }));

import { State } from '../state.js';
import { Layers } from './layers.js';

describe('GPS Track lazy loading', () => {
    beforeEach(() => {
        State.resetLayerState();
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

        expect(mocks.getGPSTrackDetails).toHaveBeenCalledWith('track-1', { signal: expect.any(AbortSignal) });
        expect(fetch).toHaveBeenCalledWith('/fresh-signed-url', { signal: expect.any(AbortSignal) });
        expect(State.gpsTrackCache.has('track-1')).toBe(true);
    });

    it('downloads and installs again when the first map layer installation fails', async () => {
        const geojson = { type: 'FeatureCollection', features: [] };
        mocks.getGPSTrackDetails.mockResolvedValue({ file: '/fresh-signed-url' });
        globalThis.fetch = vi.fn().mockResolvedValue({
            ok: true,
            json: vi.fn().mockResolvedValue(geojson),
        });
        const install = vi.spyOn(Layers, 'addGPSTrackLayer')
            .mockRejectedValueOnce(new Error('Map style is not ready'))
            .mockResolvedValue();

        await Layers.toggleGPSTrackVisibility('track-1', true);

        expect(Layers.isGPSTrackVisible('track-1')).toBe(false);
        expect(Layers.isGPSTrackLoading('track-1')).toBe(false);
        expect(State.gpsTrackCache.has('track-1')).toBe(false);

        await Layers.toggleGPSTrackVisibility('track-1', true);

        expect(mocks.getGPSTrackDetails).toHaveBeenCalledTimes(2);
        expect(fetch).toHaveBeenCalledTimes(2);
        expect(install).toHaveBeenCalledTimes(2);
        expect(install).toHaveBeenLastCalledWith('track-1', geojson, { isCurrent: expect.any(Function), prepared: { boundsCoordinates: null } });
        expect(Layers.isGPSTrackVisible('track-1')).toBe(true);
        expect(Layers.isGPSTrackLoading('track-1')).toBe(false);
        expect(State.gpsTrackCache.get('track-1')).toEqual(geojson);
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
