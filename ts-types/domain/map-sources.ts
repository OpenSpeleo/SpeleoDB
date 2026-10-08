import type { MapboxLayer, MapboxLayout } from './mapbox.ts';
import type { ViewerUpdateContext } from './viewer-updates.ts';

export interface MapSourceDefinition {
    id: string;
    label: string;
    type: 'mapbox-style' | 'raster';
    requiresToken: boolean;
    style?: string;
    tiles?: string[];
    tileSize?: number;
    maxzoom?: number;
    attribution?: string;
}
export interface RasterSourceOptions {
    type: 'raster';
    tiles: string[];
    tileSize: number | undefined;
    maxzoom: number | undefined;
    attribution: string | undefined;
}
export interface RasterLayer {
    id: string;
    type: 'raster';
    source: string;
    layout?: MapboxLayout;
}
export interface BackgroundLayer {
    id: string;
    type: 'background';
    paint: { 'background-opacity': number };
    layout?: MapboxLayout;
}
export type SourceStyleLayer = MapboxLayer | RasterLayer | BackgroundLayer;
export interface RasterStyle {
    version: number;
    glyphs: string;
    sources: { 'speleo-base-raster-source': RasterSourceOptions };
    layers: RasterLayer[];
}
export interface MapSourceMap {
    getStyle(): { layers?: SourceStyleLayer[] } | undefined;
    getLayer(id: string): unknown;
    getSource(id: string): unknown;
    addLayer(layer: SourceStyleLayer, beforeId?: string): unknown;
    removeLayer(id: string): unknown;
    addSource(id: string, source: RasterSourceOptions): unknown;
    removeSource(id: string): unknown;
    setLayoutProperty(id: string, key: 'visibility', value: 'visible' | 'none'): unknown;
    addControl(control: MapSourceControl, position: 'top-right'): unknown;
    __speleoMapSourceControl?: MapSourceControl;
}
export interface MapSourceControl {
    _container: HTMLElement | null;
    _onDocumentClick: ((event: MouseEvent) => void) | null;
    _onDocumentKeyDown: ((event: KeyboardEvent) => void) | null;
    _updateKey: object;
    _appliedSourceId: string;
    onAdd(map: MapSourceMap): HTMLElement;
    onRemove(): void;
}
export interface CheckedTileParameters { url: string }
export type CheckedTileCallback = (error: unknown, buffer?: ArrayBuffer, cacheControl?: string | null, expires?: string | null) => void;
export type CheckedTileProtocol = (parameters: CheckedTileParameters, callback: CheckedTileCallback) => { cancel(): void };
export interface CheckedFetch {
    (this: unknown, input: RequestInfo | URL, init?: RequestInit): Promise<Response>;
    __speleoCheckedTileFetch?: boolean;
    __speleoOriginalFetch?: typeof fetch;
}
export interface MapSourceChangeEvent { detail?: { reloadRequired?: boolean; sourceId?: string } }
export interface MapSourceAPI {
    applyMapSource(map: MapSourceMap, sourceId: string | null, accessToken?: string, context?: ViewerUpdateContext | null): Promise<string | null>;
}
