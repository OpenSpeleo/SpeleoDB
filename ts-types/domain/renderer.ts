import type { GlobeAtmosphereMap } from '@speleodb/map-viewer';
import type { MapControl, MapCoreMap, MapCreationOptions } from './map-core.ts';
import type { CheckedTileProtocol } from './map-sources.ts';
import type { Feature, FeatureCollection, Geometry, Point } from 'geojson';
import type { Coordinate2D, GeometryCameraMap, RendererBounds } from './map-geometry.ts';
import type { NavigationMap } from './map-runtime.ts';

/** Renderer's expression language is a recursive array, not an application record. */
export type RendererValue = string | number | boolean | null | RendererValue[] | import('maplibre-gl').ExpressionSpecification;
export interface RendererLayout {
    visibility?: 'visible' | 'none';
    'line-join'?: 'round';
    'line-cap'?: 'round';
    'icon-image'?: string;
    'icon-size'?: RendererValue;
    'icon-allow-overlap'?: boolean;
    'icon-ignore-placement'?: boolean;
    'text-field'?: RendererValue;
    'text-font'?: string[];
    'text-size'?: RendererValue;
    'text-offset'?: number[];
    'text-anchor'?: 'top';
    'text-allow-overlap'?: boolean;
    'text-ignore-placement'?: boolean;
    'symbol-placement'?: 'line';
    'text-rotation-alignment'?: 'map' | 'viewport';
    'symbol-sort-key'?: RendererValue;
    'text-variable-anchor'?: string[];
    'text-padding'?: number;
    'icon-text-fit'?: 'both';
    'icon-text-fit-padding'?: number[];
    'icon-optional'?: boolean;
    'text-optional'?: boolean;
    'icon-pitch-alignment'?: 'viewport';
    'icon-rotation-alignment'?: 'viewport';
    'text-pitch-alignment'?: 'viewport';
}
export interface RendererPaint {
    'fill-color'?: RendererValue;
    'fill-opacity'?: RendererValue;
    'line-color'?: RendererValue;
    'line-width'?: RendererValue;
    'line-opacity'?: RendererValue;
    'line-dasharray'?: number[];
    'circle-radius'?: RendererValue;
    'circle-color'?: RendererValue;
    'circle-opacity'?: RendererValue;
    'circle-stroke-width'?: RendererValue;
    'circle-stroke-color'?: RendererValue;
    'circle-stroke-opacity'?: RendererValue;
    'icon-opacity'?: RendererValue;
    'text-color'?: RendererValue;
    'text-halo-color'?: RendererValue;
    'text-halo-width'?: RendererValue;
    'text-halo-blur'?: RendererValue;
}
export interface RendererLayer {
    id: string;
    type: 'line' | 'fill' | 'circle' | 'symbol';
    source?: string;
    filter?: RendererValue;
    minzoom?: number;
    layout?: RendererLayout;
    paint?: RendererPaint;
}
export type RendererFeature = Omit<Feature<Geometry | null, unknown>, 'properties'> & { properties?: unknown };
export type RendererGeoJSON = Geometry | RendererFeature | { type: 'FeatureCollection'; features: RendererFeature[] };
export interface RendererGeoJSONSource {
    setData(data: RendererGeoJSON): unknown;
}
export interface RendererSourceOptions {
    type: 'geojson';
    data: RendererGeoJSON;
    generateId?: boolean;
    tolerance?: number;
    promoteId?: string;
}
export type RendererImage = HTMLImageElement | ImageBitmap | ImageData | { width: number; height: number; data: Uint8Array | Uint8ClampedArray };
export type RendererLngLat = Coordinate2D | { lng: number; lat: number };
export interface RendererPopup {
    once?(event: 'close', handler: () => void): unknown;
    setLngLat(coordinates: RendererLngLat): this;
    setDOMContent(content: HTMLElement): this;
    addTo(map: RendererMap): this;
    remove(): unknown;
}
export interface RendererPopupOptions {
    className: string;
    closeButton: boolean;
    closeOnClick: boolean;
    focusAfterOpen: boolean;
    maxWidth: string;
}
export interface RendererMap extends NavigationMap, GeometryCameraMap {
    getLayer(id: string): RendererLayer | undefined;
    addLayer(layer: RendererLayer): unknown;
    removeLayer(id: string): unknown;
    moveLayer(id: string): unknown;
    getSource(id: string): RendererGeoJSONSource | undefined;
    addSource(id: string, source: RendererSourceOptions): unknown;
    removeSource(id: string): unknown;
    setLayoutProperty<Key extends keyof RendererLayout>(id: string, key: Key, value: RendererLayout[Key]): unknown;
    setPaintProperty<Key extends keyof RendererPaint>(id: string, key: Key, value: RendererPaint[Key]): unknown;
    setFilter(id: string, filter: RendererValue): unknown;
    hasImage(id: string): boolean;
    loadImage(url: string): Promise<{ data: RendererImage }>;
    addImage(id: string, image: RendererImage): unknown;
    project(coordinates: readonly number[]): { x: number; y: number };
    getContainer(): HTMLElement;
}
export interface PointProperties {
    id?: string | number;
    name?: string;
    description?: string;
    color?: string;
    tag?: { id: string | number; name: string; color: string } | null;
}
export interface LandmarkPointProperties extends PointProperties { collection_color?: string | null }
export type MapPointCollection<Properties = PointProperties> = FeatureCollection<Point, Properties>;

export interface RendererMarker {
    setLngLat(coordinates: readonly number[]): this;
    addTo(map: { getContainer(): HTMLElement }): this;
    remove(): unknown;
}
export interface RendererMarkerOptions { element: HTMLElement; anchor: 'center'; opacityWhenCovered: number }

export interface RendererConstructors {
    Marker: new (options: RendererMarkerOptions) => RendererMarker;
    Map: new (options: MapCreationOptions) => MapCoreMap & GlobeAtmosphereMap;
    AttributionControl: new () => Required<MapControl>;
    NavigationControl: new () => MapControl;
    FullscreenControl: new (options?: { container: HTMLElement }) => MapControl;
    ScaleControl: new (options: { maxWidth: number; unit: 'metric' | 'imperial' }) => MapControl;
    addProtocol?: (name: string, protocol: CheckedTileProtocol) => void;
    LngLatBounds: new (southwest?: Coordinate2D, northeast?: Coordinate2D) => RendererBounds;
    Popup?: new (options: RendererPopupOptions) => RendererPopup;
}
