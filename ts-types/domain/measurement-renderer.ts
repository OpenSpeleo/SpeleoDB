import type { FeatureCollection } from 'geojson';
import type { Coordinate2D } from './map-geometry.ts';
import type { MeasurementFeature, MeasurementProperties } from './measurement.ts';
import type { MapboxImage, MapboxLayer } from './mapbox.ts';

export type MeasurementCollection = FeatureCollection<MeasurementFeature['geometry'], MeasurementProperties>;
export interface MeasurementPreview { start: Coordinate2D; end: Coordinate2D | null }
export interface MeasurementImageOptions {
    stretchX: [number, number][];
    stretchY: [number, number][];
    content: [number, number, number, number];
}
export interface MeasurementSourceDefinition { type: 'geojson'; data: MeasurementCollection; tolerance: number }
export interface MeasurementSource { setData(data: MeasurementCollection): unknown }
export interface MeasurementRendererMap {
    on(event: 'style.load', handler: () => void): unknown;
    off(event: 'style.load', handler: () => void): unknown;
    getStyle(): unknown;
    getContainer(): HTMLElement;
    getSource(id: string): MeasurementSource | undefined;
    addSource(id: string, definition: MeasurementSourceDefinition): unknown;
    removeSource(id: string): unknown;
    getLayer(id: string): MapboxLayer | undefined;
    addLayer(layer: MapboxLayer): unknown;
    removeLayer(id: string): unknown;
    hasImage(id: string): boolean;
    addImage(id: string, image: MapboxImage, options: MeasurementImageOptions): unknown;
    removeImage(id: string): unknown;
}
