/** The legend queries only rendered line depth metadata, never full feature geometry. */
export interface LegendFeature {
    layer?: { type?: string; source?: string };
    source?: string;
    properties?: { depth_val?: unknown; depth_norm?: unknown } | null;
}
export interface LegendPointerEvent { point: { x: number; y: number } }
export interface LegendMap {
    on(event: 'mousemove' | 'mouseout', handler: (event: LegendPointerEvent) => void): unknown;
    off?(event: 'mousemove' | 'mouseout', handler: (event: LegendPointerEvent) => void): unknown;
    queryRenderedFeatures(bounds: number[][]): LegendFeature[];
}
export interface LegendWindowEvent extends Event {
    detail?: { mode?: unknown; domain?: { max: number } | null; max?: unknown };
}
