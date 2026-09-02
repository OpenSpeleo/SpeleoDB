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
        State.gisLayerClickableLayerIds = new Set();
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

describe('Interactions GIS feature clicks', () => {
    function setupClick(featuresByQuery, handlers = {}) {
        const clickHandlers = [];
        const map = {
            on: vi.fn((eventName, callback) => {
                if (eventName === 'click') clickHandlers.push(callback);
            }),
            queryRenderedFeatures: vi.fn((query, options) => (
                options?.layers ? featuresByQuery.gis : featuresByQuery.general
            )),
        };
        Interactions.handlers = handlers;
        Interactions.setupClickHandlers(map);
        return { clickHandler: clickHandlers[0], clickHandlers, map };
    }

    beforeEach(() => {
        State.gisLayerClickableLayerIds = new Set([
            'gis-layer-bottom-fill',
            'gis-layer-bottom-point',
            'gis-layer-top-fill',
            'gis-layer-top-point',
        ]);
        Interactions.handlers = {};
    });

    it('opens one popup for a point rendered above an overlapping polygon', () => {
        const onGISFeatureClick = vi.fn();
        const point = { id: 'point', layer: { id: 'gis-layer-top-point' } };
        const polygon = { id: 'polygon', layer: { id: 'gis-layer-bottom-fill' } };
        const { clickHandler, map } = setupClick(
            { general: [], gis: [point, polygon] },
            { onGISFeatureClick },
        );
        const lngLat = { lng: -80, lat: 25 };

        clickHandler({ point: { x: 10, y: 20 }, lngLat });

        expect(onGISFeatureClick).toHaveBeenCalledOnce();
        expect(onGISFeatureClick).toHaveBeenCalledWith(point, lngLat);
        expect(map.queryRenderedFeatures).toHaveBeenLastCalledWith(
            { x: 10, y: 20 },
            { layers: [...State.gisLayerClickableLayerIds] },
        );
    });

    it('uses the topmost rendered feature across different GIS Layers', () => {
        const onGISFeatureClick = vi.fn();
        const topmost = { id: 'top-zone', layer: { id: 'gis-layer-top-fill' } };
        const lower = { id: 'lower-point', layer: { id: 'gis-layer-bottom-point' } };
        const { clickHandler } = setupClick(
            { general: [], gis: [topmost, lower] },
            { onGISFeatureClick },
        );

        clickHandler({ point: { x: 1, y: 2 }, lngLat: { lng: 1, lat: 2 } });

        expect(onGISFeatureClick).toHaveBeenCalledOnce();
        expect(onGISFeatureClick.mock.calls[0][0]).toBe(topmost);
    });

    it('does nothing popup-related when no clickable GIS feature is rendered', () => {
        const onGISFeatureClick = vi.fn();
        const onMapClick = vi.fn();
        const { clickHandler } = setupClick(
            { general: [], gis: [] },
            { onGISFeatureClick, onMapClick },
        );

        clickHandler({
            point: { x: 1, y: 2 },
            lngLat: { toArray: () => [1, 2] },
        });

        expect(onGISFeatureClick).not.toHaveBeenCalled();
        expect(onMapClick).toHaveBeenCalledWith([1, 2]);
    });

    it('keeps one global click handler while the style registry is replaced', () => {
        const onGISFeatureClick = vi.fn();
        const topmost = { id: 'rebuilt', layer: { id: 'gis-layer-new-point' } };
        const { clickHandler, clickHandlers, map } = setupClick(
            { general: [], gis: [topmost] },
            { onGISFeatureClick },
        );

        State.gisLayerClickableLayerIds = new Set();
        State.gisLayerClickableLayerIds.add('gis-layer-new-point');
        clickHandler({ point: { x: 1, y: 2 }, lngLat: { lng: 1, lat: 2 } });

        expect(clickHandlers).toHaveLength(1);
        expect(map.on).toHaveBeenCalledTimes(1);
        expect(onGISFeatureClick).toHaveBeenCalledOnce();
        expect(onGISFeatureClick.mock.calls[0][0]).toBe(topmost);
    });
});
