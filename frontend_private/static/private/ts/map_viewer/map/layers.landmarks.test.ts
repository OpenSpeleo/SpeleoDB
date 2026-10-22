import { landmarkColorExpression, landmarkHaloExpression } from '@speleodb/map-viewer';
import type { ViewerMap } from '../../../../../../ts-types/domain/map-state.ts';
import type { RendererLayer } from '../../../../../../ts-types/domain/renderer.ts';
import { State } from '../state.ts';
import { Layers } from './layers.ts';

describe('Layers landmark rendering', () => {
    beforeEach(() => {
        State.map = null;
        State.landmarksVisible = true;
    });

    it('colors landmark marker and label layers from collection_color', async () => {
        const addedLayers: RendererLayer[] = [];
        const mockMap = {
            on: () => undefined,
            off: () => undefined,
            getLayer: vi.fn(() => false),
            removeLayer: vi.fn(),
            getSource: vi.fn(() => false),
            removeSource: vi.fn(),
            addSource: vi.fn(),
            addLayer: vi.fn((layer: RendererLayer) => addedLayers.push(layer)),
        };
        State.map = mockMap as unknown as ViewerMap;

        Layers.addLandmarkLayer({
            type: 'FeatureCollection',
            features: [
                {
                    id: 'lm-1',
                    type: 'Feature',
                    geometry: { type: 'Point', coordinates: [-122, 45] },
                    properties: {
                        name: 'Entrance',
                        collection_color: '#123456',
                    },
                },
            ],
        });

        const markerLayer = addedLayers.find(layer => layer.id === 'landmarks-layer');
        const labelLayer = addedLayers.find(layer => layer.id === 'landmarks-labels');
        const colorExpression = landmarkColorExpression();
        const haloExpression = landmarkHaloExpression();

        expect(markerLayer!.paint!['text-color']).toEqual(colorExpression);
        expect(labelLayer!.paint!['text-color']).toEqual(colorExpression);
        expect(markerLayer!.paint!['text-halo-color']).toEqual(haloExpression);
        expect(labelLayer!.paint!['text-halo-color']).toEqual(haloExpression);
    });
});

// JSDOM cannot decode SVG images, rasterize canvas pixels, or create a WebGL
// renderer. Replace only those native boundaries; exercise the actual shared
// icon registry, layer factory, and the app's asynchronous refresh wiring.
describe('landmark icon layer integration', () => {
    beforeEach(() => {
        class DecodedImage {
            onload: (() => void) | null = null;
            onerror: (() => void) | null = null;
            crossOrigin = '';
            set src(_url: string) { queueMicrotask(() => this.onload?.()); }
        }
        vi.stubGlobal('Image', DecodedImage);
        vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
            drawImage: () => {},
            getImageData: (_x: number, _y: number, width: number, height: number) => ({
                data: new Uint8ClampedArray(width * height * 4).fill(255),
            }),
        } as unknown as CanvasRenderingContext2D);
        State.landmarksVisible = true;
    });

    afterEach(() => {
        Layers.cancelPendingWork();
        State.map = null;
        vi.restoreAllMocks();
        vi.unstubAllGlobals();
    });

    it.each(['DEFAULT', 'CAVE'] as const)('refreshes the full %s symbol policy after decoding and restores it after style replacement', async icon => {
        const layers = new Map<string, RendererLayer>();
        const sources = new Map<string, unknown>();
        const images = new Set<string>();
        const listeners = new Map<string, Set<() => void>>();
        const map = {
            on(event: string, listener: () => void) {
                const handlers = listeners.get(event) ?? new Set<() => void>();
                handlers.add(listener);
                listeners.set(event, handlers);
            },
            off: (event: string, listener: () => void) => listeners.get(event)?.delete(listener),
            getStyle: () => ({ layers: [...layers.values()] }),
            getLayer: (id: string) => layers.get(id),
            removeLayer: (id: string) => layers.delete(id),
            getSource: (id: string) => sources.get(id),
            removeSource: (id: string) => sources.delete(id),
            addSource: (id: string, source: unknown) => sources.set(id, source),
            addLayer: (layer: RendererLayer) => layers.set(layer.id, layer),
            hasImage: (id: string) => images.has(id),
            addImage: (id: string) => images.add(id),
            removeImage: (id: string) => images.delete(id),
            setLayoutProperty(id: string, key: string, value: unknown) {
                const layer = layers.get(id)!;
                Object.assign(layer.layout!, { [key]: value });
            },
        };
        State.map = map as unknown as ViewerMap;
        const data = {
            type: 'FeatureCollection' as const,
            features: [{
                type: 'Feature' as const, id: 'landmark',
                geometry: { type: 'Point' as const, coordinates: [-87, 20] },
                properties: { name: 'Landmark', icon, collection_color: '#123456' },
            }],
        };
        Layers.addLandmarkLayer(data);
        const marker = layers.get('landmarks-layer')!;
        expect(marker.layout!['text-field']).toBe('▼');
        expect(marker.layout!['icon-image']).toBeUndefined();
        // A late image decode must preserve an independent visibility change.
        marker.layout!.visibility = 'none';
        await vi.waitFor(() => expect(marker.layout!['icon-image']).toBeDefined());
        expect([...images]).toEqual([`speleodb-landmark-${icon}-123456-ffffff`]);
        expect(marker.layout).toMatchObject({
            visibility: 'none',
            'icon-allow-overlap': true, 'icon-ignore-placement': true,
            'icon-optional': true, 'text-optional': true,
        });
        const size = marker.layout!['icon-size'] as unknown[];
        expect(size.slice(0, 3)).toEqual(['interpolate', ['linear'], ['zoom']]);
        expect([size[3], size[5], size[7], size[9]]).toEqual([6, 10, 14, 18]);
        for (const [index, pixels] of [[4, 10], [6, 14], [8, 20], [10, 28]] as const) {
            const scale = size[index] as unknown[];
            expect(scale.slice(0, 2)).toEqual(['*', pixels]);
            expect(scale[2]).toBeCloseTo(1 / 24);
        }
        const policy = { ...marker.layout, visibility: 'visible' };
        const registeredImages = [...images];
        images.clear();
        layers.clear();
        sources.clear();
        for (const listener of listeners.get('style.load') ?? []) listener();
        Layers.addLandmarkLayer(data);
        await vi.waitFor(() => expect(layers.get('landmarks-layer')!.layout).toEqual(policy));
        expect([...images]).toEqual(registeredImages);
    });
});
