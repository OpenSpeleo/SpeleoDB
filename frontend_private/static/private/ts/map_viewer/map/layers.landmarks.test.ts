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
        const colorExpression = ['coalesce', ['get', 'collection_color'], '#94a3b8'];
        const haloExpression = [
            'case',
            ['==', ['get', 'collection_color'], '#ffffff'],
            '#0f172a',
            '#ffffff'
        ];

        expect(markerLayer!.paint!['text-color']).toEqual(colorExpression);
        expect(labelLayer!.paint!['text-color']).toEqual(colorExpression);
        expect(markerLayer!.paint!['text-halo-color']).toEqual(haloExpression);
        expect(labelLayer!.paint!['text-halo-color']).toEqual(haloExpression);
    });
});
