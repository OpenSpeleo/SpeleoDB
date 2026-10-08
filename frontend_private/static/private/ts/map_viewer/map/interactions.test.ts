import type { InteractionHandlers, InteractionMap, MapPointerEvent, PointerLongitudeLatitude } from '../../../../../../ts-types/domain/map-interactions.ts';
interface FixturePointer { point: { x: number; y: number }; lngLat?: Partial<PointerLongitudeLatitude>; originalEvent?: { button?: number } }
type FixtureHandler = (event: FixturePointer) => void;
interface FixtureFeature { id: string; layer: { id: string }; geometry?: { coordinates: number[] }; properties?: Record<string, never> }
import { Interactions } from './interactions.ts';
import { State } from '../state.ts';
import { Layers } from './layers.ts';

describe('GIS Geometry interaction ownership', () => {
    it('routes pointer and touch events exclusively to an active editor', () => {
        const handlers = new Map<string, ((event: MapPointerEvent) => void)[]>();
        const map = {
            on: (event: string, fn: (event: MapPointerEvent) => void) => handlers.set(event, [...(handlers.get(event) || []), fn]),
            queryRenderedFeatures: vi.fn(() => []),
            getCanvas: () => ({ style: {} }),
        };
        const editor = {
            isActive: vi.fn(() => true), handleClick: vi.fn(), handleMouseDown: vi.fn(),
            handleMouseMove: vi.fn(), handleMouseUp: vi.fn(), handleContextMenu: vi.fn(), handleCancel: vi.fn(),
        };
        const onMapClick = vi.fn();
        Interactions.init(map as unknown as InteractionMap, { geometryEditor: editor, onMapClick });
        const event: MapPointerEvent = { point: { x: 1, y: 1 }, lngLat: { lng: 0, lat: 0, toArray: () => [0, 0] }, originalEvent: { button: 0 } };
        for (const name of ['mousedown', 'mousemove', 'mouseup', 'click', 'contextmenu', 'touchstart', 'touchmove', 'touchend', 'touchcancel']) {
            handlers.get(name)!.forEach(fn => fn(event));
        }
        expect(editor.handleMouseMove).toHaveBeenCalledTimes(2);
        expect(editor.handleMouseDown).toHaveBeenCalledTimes(2);
        expect(editor.handleMouseUp).toHaveBeenCalledTimes(2);
        expect(editor.handleCancel).toHaveBeenCalledOnce();
        expect(editor.handleClick).toHaveBeenCalledOnce();
        expect(editor.handleContextMenu).toHaveBeenCalledOnce();
        expect(map.queryRenderedFeatures).not.toHaveBeenCalled();
        expect(onMapClick).not.toHaveBeenCalled();
        editor.isActive.mockReturnValue(false);
        handlers.get('click')!.forEach(fn => fn(event));
        expect(onMapClick).toHaveBeenCalledWith([0, 0]);
        Interactions.handlers = {};
    });
});

describe('Interactions landmark dragging', () => {
    function createMap(features: FixtureFeature[]) {
        const handlers: Record<string, FixtureHandler> = {};
        const canvas = { style: {} };
        const map = {
            on: vi.fn((eventName: string, callback: (event: MapPointerEvent) => void) => {
                handlers[eventName] = callback as FixtureHandler;
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

        Interactions.setupDragHandlers(map as unknown as InteractionMap);
        handlers.mousedown!({
            originalEvent: { button: 0 },
            point: { x: 10, y: 10 },
        });
        handlers.mousemove!({
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

        Interactions.setupDragHandlers(map as unknown as InteractionMap);
        handlers.mousedown!({
            originalEvent: { button: 0 },
            point: { x: 10, y: 10 },
        });
        handlers.mousemove!({
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

        Interactions.setupDragHandlers(map as unknown as InteractionMap);
        handlers.mousedown!({
            originalEvent: { button: 0 },
            point: { x: 10, y: 10 },
        });
        handlers.mousemove!({
            point: { x: 50, y: 10 },
            lngLat: { lng: -123, lat: 46 },
        });

        expect(map.dragPan.disable).toHaveBeenCalledTimes(1);
        expect(onLandmarkDrag).toHaveBeenCalledWith('lm-1', [-123, 46]);
    });

    it('cancels a moved landmark on tool handoff and restores the original gesture state', () => {
        State.allLandmarks.set('lm-1', { id: 'lm-1', can_write: true });
        const { map, handlers } = createMap([landmarkFeature()]);
        const onLandmarkDrag = vi.fn();
        const onLandmarkDragEnd = vi.fn();
        const restore = vi.spyOn(Layers, 'revertLandmarkPosition').mockImplementation(() => {});
        Interactions.handlers = { onLandmarkDrag, onLandmarkDragEnd };
        try {
            Interactions.setupDragHandlers(map as unknown as InteractionMap);
            handlers.mousedown!({ originalEvent: { button: 0 }, point: { x: 10, y: 10 } });
            handlers.mousemove!({ point: { x: 50, y: 10 }, lngLat: { lng: -123, lat: 46 } });
            expect(onLandmarkDrag).toHaveBeenCalledWith('lm-1', [-123, 46]);
            const tool = { isActive: () => true, handleClick: vi.fn() };
            Interactions.handlers.measurementTool = tool;
            const event: MapPointerEvent = { point: { x: 50, y: 10 }, lngLat: { lng: -123, lat: 46, toArray: () => [-123, 46] }, originalEvent: { button: 0 } };
            expect(Interactions.dispatchToActiveTool('handleClick', event)).toBe(true);
            expect(restore).toHaveBeenCalledWith('lm-1', [-122, 45]);
            expect(map.dragPan.enable).toHaveBeenCalledOnce();
            expect(map.doubleClickZoom.enable).toHaveBeenCalledOnce();
            expect(tool.handleClick).toHaveBeenCalledWith(event);
            Interactions.handlers.measurementTool = { isActive: () => false };
            handlers.mouseup!(event);
            expect(onLandmarkDragEnd).not.toHaveBeenCalled();
            Interactions.cancelPendingDrag!();
            expect(restore).toHaveBeenCalledOnce();
        } finally { restore.mockRestore(); Interactions.handlers = {}; }
    });
});

describe('Interactions GIS feature clicks', () => {
    function setupClick(featuresByQuery: { gis: FixtureFeature[]; general: FixtureFeature[] }, handlers: InteractionHandlers = {}) {
        const clickHandlers: FixtureHandler[] = [];
        const map = {
            on: vi.fn((eventName: string, callback: (event: MapPointerEvent) => void) => {
                if (eventName === 'click') clickHandlers.push(callback as FixtureHandler);
            }),
            queryRenderedFeatures: vi.fn((query: unknown, options?: { layers: string[] }) => (
                options?.layers ? featuresByQuery.gis : featuresByQuery.general
            )),
        };
        Interactions.handlers = handlers;
        Interactions.setupClickHandlers(map as unknown as InteractionMap);
        return { clickHandler: clickHandlers[0]!, clickHandlers, map };
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
        expect(onGISFeatureClick.mock.calls[0]![0]).toBe(topmost);
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
        expect(onGISFeatureClick.mock.calls[0]![0]).toBe(topmost);
    });
});
