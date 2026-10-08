import type { MapControl, MapCoreMap, MapCreationOptions } from './map-core.ts';
import type { CheckedTileProtocol } from './map-sources.ts';
import type { Feature, FeatureCollection, Geometry, Point } from 'geojson';
import type { Coordinate2D, GeometryCameraMap, MapboxBounds } from './map-geometry.ts';
import type { NavigationMap } from './map-runtime.ts';

/** Mapbox's expression language is a recursive array, not an application record. */
export type MapboxValue = string | number | boolean | null | MapboxValue[];
export interface MapboxLayout {
    visibility?: 'visible' | 'none';
    'line-join'?: 'round';
    'line-cap'?: 'round';
    'icon-image'?: string;
    'icon-size'?: MapboxValue;
    'icon-allow-overlap'?: boolean;
    'icon-ignore-placement'?: boolean;
    'text-field'?: MapboxValue;
    'text-font'?: string[];
    'text-size'?: MapboxValue;
    'text-offset'?: number[];
    'text-anchor'?: 'top';
    'text-allow-overlap'?: boolean;
    'text-ignore-placement'?: boolean;
    'symbol-placement'?: 'line';
    'text-rotation-alignment'?: 'map' | 'viewport';
    'symbol-sort-key'?: MapboxValue;
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
export interface MapboxPaint {
    'fill-color'?: MapboxValue;
    'fill-opacity'?: MapboxValue;
    'line-color'?: MapboxValue;
    'line-width'?: MapboxValue;
    'line-opacity'?: MapboxValue;
    'line-dasharray'?: number[];
    'circle-radius'?: MapboxValue;
    'circle-color'?: MapboxValue;
    'circle-opacity'?: MapboxValue;
    'circle-stroke-width'?: MapboxValue;
    'circle-stroke-color'?: MapboxValue;
    'circle-stroke-opacity'?: MapboxValue;
    'icon-opacity'?: MapboxValue;
    'text-color'?: MapboxValue;
    'text-halo-color'?: MapboxValue;
    'text-halo-width'?: MapboxValue;
    'text-halo-blur'?: MapboxValue;
}
export interface MapboxLayer {
    id: string;
    type: 'line' | 'fill' | 'circle' | 'symbol';
    source?: string;
    filter?: MapboxValue;
    minzoom?: number;
    layout?: MapboxLayout;
    paint?: MapboxPaint;
}
export type MapboxFeature = Omit<Feature<Geometry | null, unknown>, 'properties'> & { properties?: unknown };
export type MapboxGeoJSON = Geometry | MapboxFeature | { type: 'FeatureCollection'; features: MapboxFeature[] };
export interface MapboxGeoJSONSource<Data extends MapboxGeoJSON = MapboxGeoJSON> {
    _data?: Data;
    setData(data: MapboxGeoJSON): unknown;
}
export interface MapboxSourceOptions {
    type: 'geojson';
    data: MapboxGeoJSON;
    generateId?: boolean;
    tolerance?: number;
    promoteId?: string;
}
export type MapboxImage = HTMLImageElement | ImageBitmap | ImageData | { width: number; height: number; data: Uint8Array | Uint8ClampedArray };
export type MapboxLngLat = Coordinate2D | { lng: number; lat: number };
export interface MapboxPopup {
    once?(event: 'close', handler: () => void): unknown;
    setLngLat(coordinates: MapboxLngLat): this;
    setDOMContent(content: HTMLElement): this;
    addTo(map: MapboxMap): this;
    remove(): unknown;
}
export interface MapboxPopupOptions {
    className: string;
    closeButton: boolean;
    closeOnClick: boolean;
    focusAfterOpen: boolean;
    maxWidth: string;
}
export interface MapboxMap extends NavigationMap, GeometryCameraMap {
    getLayer(id: string): MapboxLayer | undefined;
    addLayer(layer: MapboxLayer): unknown;
    removeLayer(id: string): unknown;
    moveLayer(id: string): unknown;
    getSource<Data extends MapboxGeoJSON = MapboxGeoJSON>(id: string): MapboxGeoJSONSource<Data> | undefined;
    addSource(id: string, source: MapboxSourceOptions): unknown;
    removeSource(id: string): unknown;
    setLayoutProperty<Key extends keyof MapboxLayout>(id: string, key: Key, value: MapboxLayout[Key]): unknown;
    setPaintProperty<Key extends keyof MapboxPaint>(id: string, key: Key, value: MapboxPaint[Key]): unknown;
    setFilter(id: string, filter: MapboxValue): unknown;
    hasImage(id: string): boolean;
    loadImage(url: string, callback: (error: Error | null, image?: MapboxImage) => void): unknown;
    addImage(id: string, image: MapboxImage): unknown;
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

export interface MapboxMarker {
    setLngLat(coordinates: readonly number[]): this;
    addTo(map: { getContainer(): HTMLElement }): this;
    remove(): unknown;
}
export interface MapboxMarkerOptions { element: HTMLElement; anchor: 'center'; occludedOpacity: number }

export interface MapboxConstructors {
    Marker: new (options: MapboxMarkerOptions) => MapboxMarker;
    accessToken: string;
    Map: new (options: MapCreationOptions) => MapCoreMap;
    NavigationControl: new () => MapControl;
    FullscreenControl: new (options?: { container: HTMLElement }) => MapControl;
    ScaleControl: new (options: { maxWidth: number; unit: 'metric' | 'imperial' }) => MapControl;
    addProtocol?: (name: string, protocol: CheckedTileProtocol) => void;
    LngLatBounds: new (southwest?: Coordinate2D, northeast?: Coordinate2D) => MapboxBounds;
    Popup?: new (options: MapboxPopupOptions) => MapboxPopup;
}
