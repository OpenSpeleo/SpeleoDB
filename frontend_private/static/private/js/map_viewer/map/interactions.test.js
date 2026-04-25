import { Interactions } from './interactions.js';
import { State } from '../state.js';

describe('Interactions landmark dragging', () => {
    function createMap(features) {
        const handlers = {};
        const canvas = { style: {} };
        const map = {
            on: vi.fn((eventName, callback) => {
                handlers[eventName] = callback;
            }),
            queryRenderedFeatures: vi.fn(() => features),
            getCanvas: vi.fn(() => canvas),
            dragPan: {
                disable: vi.fn(),
                enable: vi.fn(),
            },
            doubleClickZoom: {
                disable: vi.fn(),
                enable: vi.fn(),
            },
        };

        return { map, handlers };
    }

    function landmarkFeature(id = 'lm-1') {
        return {
            id,
            layer: { id: 'landmarks-layer' },
            geometry: { coordinates: [-122, 45] },
            properties: {},
        };
    }

    beforeEach(() => {
        State.allLandmarks = new Map();
        Interactions.handlers = {};
    });

    it('does not start landmark drag when permission state is missing', () => {
        const { map, handlers } = createMap([landmarkFeature()]);
        const onLandmarkDrag = vi.fn();
        Interactions.handlers = { onLandmarkDrag };

        Interactions.setupDragHandlers(map);
        handlers.mousedown({
            originalEvent: { button: 0 },
            point: { x: 10, y: 10 },
        });
        handlers.mousemove({
            point: { x: 50, y: 10 },
            lngLat: { lng: -123, lat: 46 },
        });

        expect(map.dragPan.disable).not.toHaveBeenCalled();
        expect(onLandmarkDrag).not.toHaveBeenCalled();
    });

    it('does not start landmark drag without explicit write permission', () => {
        State.allLandmarks.set('lm-1', { id: 'lm-1', can_write: false });
        const { map, handlers } = createMap([landmarkFeature()]);
        const onLandmarkDrag = vi.fn();
        Interactions.handlers = { onLandmarkDrag };

        Interactions.setupDragHandlers(map);
        handlers.mousedown({
            originalEvent: { button: 0 },
            point: { x: 10, y: 10 },
        });
        handlers.mousemove({
            point: { x: 50, y: 10 },
            lngLat: { lng: -123, lat: 46 },
        });

        expect(map.dragPan.disable).not.toHaveBeenCalled();
        expect(onLandmarkDrag).not.toHaveBeenCalled();
    });

    it('starts landmark drag only with explicit write permission', () => {
        State.allLandmarks.set('lm-1', { id: 'lm-1', can_write: true });
        const { map, handlers } = createMap([landmarkFeature()]);
        const onLandmarkDrag = vi.fn();
        Interactions.handlers = { onLandmarkDrag };

        Interactions.setupDragHandlers(map);
        handlers.mousedown({
            originalEvent: { button: 0 },
            point: { x: 10, y: 10 },
        });
        handlers.mousemove({
            point: { x: 50, y: 10 },
            lngLat: { lng: -123, lat: 46 },
        });

        expect(map.dragPan.disable).toHaveBeenCalledTimes(1);
        expect(onLandmarkDrag).toHaveBeenCalledWith('lm-1', [-123, 46]);
    });
});
