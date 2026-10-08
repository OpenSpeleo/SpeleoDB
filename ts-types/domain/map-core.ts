import type { MapboxMap } from './mapbox.ts';
import type { MapSourceMap, RasterStyle } from './map-sources.ts';

export interface MapCoreOptions {
    fullscreenContainer?: HTMLElement;
}
export interface MapCreationOptions {
    container: string;
    style: string | RasterStyle;
    center: number[];
    zoom: number;
    projection: 'globe';
    pitchWithRotate: boolean;
    dragRotate: boolean;
    touchPitch: boolean;
}
export interface MapControl { onAdd?(map: MapCoreMap): HTMLElement; onRemove?(): void }
export type MapCoreMap = MapboxMap & MapSourceMap & {
    on(event: 'load' | 'style.load' | 'remove', callback: () => void): unknown;
    resize(): unknown;
    addControl(control: MapControl, position: 'top-right' | 'bottom-right'): unknown;
};
