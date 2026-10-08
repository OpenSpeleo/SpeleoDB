import type { TransformStyleFunction } from 'maplibre-gl';
import type { RendererMap } from './renderer.ts';
import type { MapSourceMap, RasterStyle } from './map-sources.ts';

export interface MapCoreOptions {
    fullscreenContainer?: HTMLElement;
}
export interface MapCreationOptions {
    container: string;
    style: string | RasterStyle | null;
    center: number[];
    zoom: number;
    transformRequest(url: string): { url: string };
    attributionControl: false;
    pitchWithRotate: boolean;
    dragRotate: boolean;
    touchPitch: boolean;
}
export interface MapControl { onAdd?(map: MapCoreMap): HTMLElement; onRemove?(): void }
export type MapCoreMap = RendererMap & MapSourceMap & {
    on(event: 'load' | 'style.load' | 'remove', callback: () => void): unknown;
    resize(): unknown;
    jumpTo(options: { center: number[]; zoom: number }): unknown;
    setStyle(style: string | RasterStyle, options: { transformStyle: TransformStyleFunction }): unknown;
    addControl(control: MapControl, position: 'top-right' | 'bottom-right' | 'bottom-left'): unknown;
};
