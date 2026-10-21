import { createCoordinateBounds, decodeGeoJSONBBox } from '@speleodb/map-core/coordinate-bounds';
import type { CoordinateBounds, CoordinateBoundsAccumulator } from '@speleodb/map-core/coordinate-bounds';
import { createPreparationRunner, transformGeometrySteps } from '@speleodb/map-core/preparation';
import { clipSurveyGeoJSONSteps } from '@speleodb/map-core/survey-clipping';
import type { FeatureCollection, Geometry } from 'geojson';
import type { JSONObject } from '../../../../../../ts-types/domain/json.ts';
import type { BoundsPreparationOptions, PreparationOptions, PreparedProject, PreparedSnapPoint } from '../../../../../../ts-types/domain/map-preparation.ts';
import type { DisplayGeometry, DisplayGeometryType, ViewerFeature, ViewerGeoJSON } from '../../../../../../ts-types/domain/map-geometry.ts';
import { DEFAULTS } from '../config.ts';
import { DepthUtils, resolveLineDepthValue } from './depth.ts';
import { GEOMETRY_TYPES, GIS_GEOMETRY_TYPE_PROPERTY } from './gis_layer_geometry.ts';

const runPreparation = createPreparationRunner({ budgetMs: DEFAULTS.VIEWER_WORK.BUDGET_MS });

/** Public-view opt-in; clipping precedes all derived survey metadata. */
export function clipProjectGeoJSON(data: ViewerGeoJSON, bound: unknown, options: PreparationOptions = {}): Promise<ViewerGeoJSON> {
    return runPreparation(clipSurveyGeoJSONSteps(data, bound), options);
}

function* prepareGeometry<G extends Geometry | null | undefined>(geometry: G, bounds: CoordinateBoundsAccumulator, flatten: boolean): Generator<void, G, unknown> {
    return yield* transformGeometrySteps(geometry, {
        visitPosition: bounds.extend,
        flattenAltitude: flatten,
    });
}

function* boundsSteps(data: ViewerGeoJSON | null | undefined, wrapLongitude: boolean): Generator<void, CoordinateBounds | null, unknown> {
    const bounds = createCoordinateBounds({ bbox: decodeGeoJSONBBox(data?.bbox), wrapLongitude });
    if (!bounds.bbox) {
        if (data?.type === 'FeatureCollection') {
            for (const feature of data.features || []) {
                yield* prepareGeometry(feature?.geometry, bounds, false);
                yield;
            }
        } else {
            yield* prepareGeometry(data?.type === 'Feature' ? data.geometry : data, bounds, false);
        }
    }
    return yield* bounds.finishSteps();
}

/** Return a portable [[west, south], [east, north]] pair, or null. */
export function prepareGeoJSONBounds(data: ViewerGeoJSON | null | undefined, { wrapLongitude = true, ...options }: BoundsPreparationOptions = {}) {
    return runPreparation(boundsSteps(data, wrapLongitude), options);
}

function* projectSteps<Data extends ViewerGeoJSON | null | undefined>(raw: Data): Generator<void, PreparedProject<Data>, unknown> {
    if (!Array.isArray((raw as FeatureCollection | null | undefined)?.features)) return { data: raw, domain: null, snapPoints: [], boundsCoordinates: null };
    // The existing array guard establishes the project collection contract.
    const collection = raw as FeatureCollection<Geometry | null, JSONObject | null>;
    const sections = new Map<unknown, { sum: number; count: number }>();
    for (const feature of collection.features) {
        if (feature?.geometry?.type === 'Point') {
            const section = DepthUtils.getFeatureSectionName(feature.properties);
            const depth = DepthUtils.getFeatureDepthValue(feature.properties);
            if (section != null && Number.isFinite(depth)) {
                const entry = sections.get(section) || { sum: 0, count: 0 };
                entry.sum += depth!;
                entry.count += 1;
                sections.set(section, entry);
            }
        }
        yield;
    }
    const averages = new Map<unknown, number>();
    let maximum = -Infinity;
    for (const [section, { sum, count }] of sections) {
        const average = sum / count;
        averages.set(section, average);
        if (Number.isFinite(average)) maximum = Math.max(maximum, average);
        yield;
    }
    for (const feature of collection.features) {
        if (feature?.geometry?.type === 'LineString') {
            const depth = resolveLineDepthValue(feature.properties, averages);
            if (Number.isFinite(depth)) maximum = Math.max(maximum, depth!);
        }
        yield;
    }
    const domain = Number.isFinite(maximum) ? { min: 0, max: Math.max(0, maximum) } : null;
    const denominator = domain ? Math.max(DEFAULTS.DEPTH.ZERO_DOMAIN_MAX_FEET, domain.max) : 1;
    const bounds = createCoordinateBounds({ bbox: decodeGeoJSONBBox(raw?.bbox) });
    const features: ViewerFeature[] = [];
    const snapPoints: PreparedSnapPoint[] = [];
    for (let index = 0; index < collection.features.length; index += 1) {
        const original = collection.features[index];
        if (!original) {
            features.push(original!);
            yield;
            continue;
        }
        const feature = { ...original, geometry: yield* prepareGeometry(original.geometry, bounds, true) };
        if (feature.geometry?.type === 'LineString') {
            if (feature.properties) {
                feature.properties = { ...feature.properties };
                const depth = resolveLineDepthValue(feature.properties, averages);
                if (Number.isFinite(depth)) {
                    feature.properties.depth_val = depth!;
                    feature.properties.depth_norm = Math.min(Math.max(depth! / denominator, 0), 1);
                } else {
                    delete feature.properties.depth_val;
                    delete feature.properties.depth_norm;
                }
            }
            const coords = feature.geometry.coordinates;
            if (coords?.length >= 2) {
                const lineName = feature.properties?.section_name || feature.properties?.name || `Line ${index}`;
                snapPoints.push(
                    { coordinates: [coords[0]![0]!, coords[0]![1]!], lineName, type: 'start', lineIndex: 0 },
                    { coordinates: [coords.at(-1)![0]!, coords.at(-1)![1]!], lineName, type: 'end', lineIndex: coords.length - 1 },
                );
            }
        }
        features.push(feature);
        yield;
    }
    return { data: { ...raw, features }, domain, snapPoints, boundsCoordinates: yield* bounds.finishSteps() };
}

/** Immutable preparation; callers publish the complete result only if still current. */
export function prepareProjectGeoJSON<Data extends ViewerGeoJSON | null | undefined>(data: Data, options?: PreparationOptions) {
    return runPreparation(projectSteps(data), options);
}

function* gisSteps(geojson: ViewerGeoJSON | null | undefined) {
    const features: FeatureCollection<DisplayGeometry, JSONObject>['features'] = [];
    const found = new Set<DisplayGeometryType>();
    function* append(geometry: Geometry | null | undefined, feature?: ViewerFeature): Generator<void, void, unknown> {
        if (!geometry) return;
        if (geometry.type === 'GeometryCollection') {
            for (const child of geometry.geometries || []) {
                yield* append(child, feature);
                yield;
            }
        } else if (GEOMETRY_TYPES.includes(geometry.type)) {
            found.add(geometry.type);
            features.push({
                ...feature, type: 'Feature', geometry,
                properties: { ...feature?.properties, [GIS_GEOMETRY_TYPE_PROPERTY]: geometry.type },
            });
            yield;
        }
    }
    if (geojson?.type === 'FeatureCollection') {
        for (const feature of geojson.features || []) {
            yield* append(feature.geometry, feature);
            yield;
        }
    } else {
        yield* append(geojson?.type === 'Feature' ? geojson.geometry : geojson, geojson?.type === 'Feature' ? geojson : undefined);
    }
    return {
        data: { type: 'FeatureCollection' as const, features },
        geometryTypes: GEOMETRY_TYPES.filter(type => found.has(type)),
    };
}

/** GIS display annotations preserve cached coordinates and yield per feature. */
export function prepareGISLayerGeoJSONAsync(data: ViewerGeoJSON | null | undefined, options?: PreparationOptions) {
    return runPreparation(gisSteps(data), options);
}
