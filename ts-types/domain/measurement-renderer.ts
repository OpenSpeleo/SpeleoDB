import type { FeatureCollection } from 'geojson';
import type { Coordinate2D } from './map-geometry.ts';
import type { MeasurementFeature, MeasurementProperties } from './measurement.ts';
import type { RendererImage, RendererLayer } from './renderer.ts';

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
    getLayer(id: string): RendererLayer | undefined;
    addLayer(layer: RendererLayer): unknown;
    removeLayer(id: string): unknown;
    hasImage(id: string): boolean;
    addImage(id: string, image: RendererImage, options: MeasurementImageOptions): unknown;
    removeImage(id: string): unknown;
}
