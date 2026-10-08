import type { ViewerMap } from '../../../../../../ts-types/domain/map-state.ts';
import { Layers } from './layers.ts';
import { State } from '../state.ts';

afterEach(() => { State.resetLayerState(); State.map = null; });

it('yields during layer moves and stops an obsolete ordering before touching more layers', async () => {
    const ids = Array.from({ length: 200 }, (_, index) => `gps-track-line-${index}`);
    State.allGPSTrackLayers.set('fixture', ids);
    let sliceWork = 0;
    let current = true;
    const context = {
        isCurrent: () => current,
        shouldYield: () => sliceWork >= 8,
        yield: vi.fn(async () => {
            expect(sliceWork).toBe(8);
            sliceWork = 0;
            current = false;
            return false;
        }),
    };
    const moveLayer = vi.fn(() => { sliceWork++; });
    State.map = {
        getStyle: () => { throw new Error('Do not serialize source geometry to order layers'); },
        getLayer: (id: string) => ids.includes(id),
        moveLayer,
    } as unknown as ViewerMap;
    await Layers.reorderLayersNow(context);
    expect(context.yield).toHaveBeenCalledOnce();
    expect(moveLayer).toHaveBeenCalledTimes(8);
});

it('keeps overlay, survey, measurement and draft ordering across multiple work slices', async () => {
    const ids = ['gis-geometry-draft-vertices', 'landmarks-layer', 'stations-p-labels',
        'gps-track-points-a', 'gis-layer-a-line', 'gps-track-line-a', 'stations-p-circles'];
    State.allProjectLayers.set('fixture', ids);
    const moves: string[] = [];
    State.map = {
        getStyle: () => { throw new Error('Do not serialize source geometry to order layers'); },
        getLayer: (id: string) => ids.includes(id),
        moveLayer: (id: string) => moves.push(id),
    } as unknown as ViewerMap;
    const context = { isCurrent: () => true, shouldYield: () => true, yield: vi.fn(async () => true) };
    await Layers.reorderLayersNow(context);
    expect(context.yield.mock.calls.length).toBeGreaterThan(ids.length);
    expect(moves).toEqual(['gps-track-line-a', 'gps-track-points-a', 'gis-layer-a-line',
        'stations-p-circles', 'stations-p-labels', 'landmarks-layer', 'gis-geometry-draft-vertices']);
});
