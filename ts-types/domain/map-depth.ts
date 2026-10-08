import type { Feature, Geometry } from 'geojson';

/** Survey files accept these historical field spellings and coerce their values. */
export interface DepthProperties {
    section_name?: unknown;
    SECTION_NAME?: unknown;
    section?: unknown;
    Section?: unknown;
    name?: unknown;
    Name?: unknown;
    depth?: unknown;
    Depth?: unknown;
    depth_m?: unknown;
    depth_ft?: unknown;
    DEPTH?: unknown;
}

export type DepthFeature = Feature<Geometry | null, DepthProperties | null>;
export type SectionDepthMap = Map<unknown, number>;
export type DepthPaint = ['case', ['has', 'depth_val'], [
    'interpolate', ['linear'], ['max', 0, ['coalesce', ['to-number', ['get', 'depth_val']], 0]],
    ...(number | string)[],
], string];
export type SurveyPaint = string | ['to-color', ['get', 'color'], string] | DepthPaint;
