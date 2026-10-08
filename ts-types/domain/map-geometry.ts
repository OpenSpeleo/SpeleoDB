import type { Feature, FeatureCollection, Geometry } from 'geojson';
import type { JSONObject } from './json.ts';
import type { RendererConstructors } from './renderer.ts';

export type ViewerFeature = Feature<Geometry | null, JSONObject | null>;
export type ViewerGeoJSON = FeatureCollection<Geometry | null, JSONObject | null> | ViewerFeature | Geometry;
export type DisplayGeometry = Exclude<Geometry, { type: 'GeometryCollection' }>;
export type DisplayGeometryType = DisplayGeometry['type'];
export type RenderGeometryType = 'Point' | 'LineString' | 'Polygon';
export type Coordinate2D = readonly [number, number];

export interface RendererBounds {
    extend(coordinates: Coordinate2D | CameraBounds): this;
    isEmpty(): boolean;
}

export type RendererGlobal = RendererConstructors;

export interface Rectangle {
    left: number;
    right: number;
    top: number;
    bottom: number;
}

export interface CameraPadding {
    left: number;
    right: number;
    top: number;
    bottom: number;
}

export type FlatBounds = readonly [number, number, number, number];
export type CameraBounds = RendererBounds | FlatBounds | readonly [Coordinate2D, Coordinate2D];

export interface GeometryCameraMap {
    getContainer?(): HTMLElement | null;
    fitBounds(bounds: CameraBounds, options: {
        padding: number | CameraPadding;
        maxZoom: number;
        bearing?: number;
        pitch?: number;
        retainPadding?: boolean;
    }): unknown;
}

export type ZoomInterpolation = ['interpolate', ['linear'], ['zoom'], ...number[]];
export type GeometryFilter =
    | ['==', string, RenderGeometryType]
    | ['all', ['==', ['geometry-type'], RenderGeometryType], ['in', ['get', string], ['literal', DisplayGeometryType[]]]];

interface OverlayLayerBase {
    id: string;
    source: string;
    filter: GeometryFilter;
}

export type OverlayLayer = OverlayLayerBase & (
    | { type: 'fill'; layout: { visibility: 'visible' }; paint: { 'fill-color': string; 'fill-opacity': number } }
    | { type: 'line'; layout: { visibility: 'visible'; 'line-join'?: 'round'; 'line-cap'?: 'round' }; paint: { 'line-color': string; 'line-width': ZoomInterpolation; 'line-opacity': number } }
    | { type: 'circle'; layout: { visibility: 'visible' }; paint: { 'circle-color': string; 'circle-radius': ZoomInterpolation; 'circle-stroke-color': string; 'circle-stroke-width': number } }
);

export interface OverlaySource {
    type: 'geojson';
    data: ViewerGeoJSON;
    generateId: boolean;
    tolerance: number;
}

export interface VectorOverlayMap {
    addSource(id: string, source: OverlaySource): unknown;
    addLayer(layer: OverlayLayer): unknown;
}
