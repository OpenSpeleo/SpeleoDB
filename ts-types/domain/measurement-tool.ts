import type { MeasurementPickingMap, ScreenPoint } from './measurement.ts';
import type { MeasurementRendererMap } from './measurement-renderer.ts';
export interface MeasurementToolMap extends MeasurementPickingMap, MeasurementRendererMap {
    on(event: 'style.load' | 'move' | 'remove', handler: () => void): unknown;
    off(event: 'style.load' | 'move' | 'remove', handler: () => void): unknown;
    getCanvas(): HTMLCanvasElement;
    doubleClickZoom?: { isEnabled?(): boolean; enable(): void; disable(): void };
}
export interface MeasurementInput {
    point?: ScreenPoint;
    points?: ScreenPoint[];
    originalEvent?: {
        button?: number;
        detail?: number;
        touches?: { length: number };
        sourceCapabilities?: { firesTouchEvents?: boolean } | null;
        preventDefault?(): void;
    };
    preventDefault?(): void;
}
export interface MeasurementGesture { invalid: boolean; point?: ScreenPoint | undefined }
export interface MeasurementOptions { canActivate?: () => boolean; onActivate?: () => void }
