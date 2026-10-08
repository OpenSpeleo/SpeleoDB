import { createPreparationRunner, transformGeometrySteps } from '@speleodb/map-core/preparation';
import type { FeatureCollection, Geometry, Position } from 'geojson';
import type { JSONObject } from '../../../../../../ts-types/domain/json.ts';
import type { BoundedData, BoundsPreparationOptions, PreparationBounds, PreparationOptions, PreparedBounds, PreparedProject, PreparedSnapPoint } from '../../../../../../ts-types/domain/map-preparation.ts';
import type { DisplayGeometry, DisplayGeometryType, ViewerFeature, ViewerGeoJSON } from '../../../../../../ts-types/domain/map-geometry.ts';
import { DEFAULTS } from '../config.ts';
import { DepthUtils, resolveLineDepthValue } from './depth.ts';
import { GEOMETRY_TYPES, GIS_GEOMETRY_TYPE_PROPERTY } from './gis_layer_geometry.ts';

const runPreparation = createPreparationRunner({ budgetMs: DEFAULTS.VIEWER_WORK.BUDGET_MS });

function readBBox(data: BoundedData | null | undefined): PreparedBounds | null {
    const bbox = data?.bbox;
    if (!Array.isArray(bbox) || bbox.length < 4 || bbox.length % 2 || !bbox.every(Number.isFinite)) return null;
    const dimensions = bbox.length / 2;
    const west = bbox[0];
    const east = bbox[dimensions]! < west ? bbox[dimensions]! + DEFAULTS.MAP.ANTIMERIDIAN_WRAP_DEGREES : bbox[dimensions]!;
    return [[west, bbox[1]], [east, bbox[dimensions + 1]!]];
}

function createBounds(data: BoundedData | null | undefined, wrapLongitude: boolean): PreparationBounds {
    return {
        bbox: readBBox(data), wrapLongitude, longitudes: [],
        west: Infinity, east: -Infinity, south: Infinity, north: -Infinity,
    };
}

function extendBounds(bounds: PreparationBounds, coordinates: Position) {
    if (bounds.bbox) return;
    const [longitude, latitude] = coordinates as [number, number, ...number[]];
    if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) return;
    if (bounds.wrapLongitude) {
        const fullTurn = DEFAULTS.MAP.ANTIMERIDIAN_WRAP_DEGREES;
        bounds.longitudes.push(((longitude % fullTurn) + fullTurn) % fullTurn);
    } else {
        bounds.west = Math.min(bounds.west, longitude);
        bounds.east = Math.max(bounds.east, longitude);
    }
    bounds.south = Math.min(bounds.south, latitude);
    bounds.north = Math.max(bounds.north, latitude);
}

/** Bottom-up merge sort avoids a single uninterruptible Array.sort call. */
function* sortLongitudes(values: number[]): Generator<void, number[], unknown> {
    let sorted = values;
    let scratch = new Array<number>(values.length);
    for (let width = 1; width < values.length; width *= 2) {
        for (let start = 0; start < values.length; start += width * 2) {
            const middle = Math.min(start + width, values.length);
            const end = Math.min(start + width * 2, values.length);
            let left = start;
            let right = middle;
            for (let out = start; out < end; out += 1) {
                scratch[out] = left < middle && (right >= end || sorted[left]! <= sorted[right]!)
                    ? sorted[left++]! : sorted[right++]!;
                yield;
            }
        }
        [sorted, scratch] = [scratch, sorted];
    }
    return sorted;
}

function* finishBounds(bounds: PreparationBounds): Generator<void, PreparedBounds | null, unknown> {
    if (bounds.bbox) return bounds.bbox;
    if (!Number.isFinite(bounds.south)) return null;
    if (!bounds.wrapLongitude) return [[bounds.west, bounds.south], [bounds.east, bounds.north]];
    const longitudes = yield* sortLongitudes(bounds.longitudes);
    const fullTurn = DEFAULTS.MAP.ANTIMERIDIAN_WRAP_DEGREES;
    let largestGap = -Infinity;
    let gapIndex = 0;
    for (let index = 0; index < longitudes.length; index += 1) {
        const next = index === longitudes.length - 1 ? longitudes[0]! + fullTurn : longitudes[index + 1]!;
        const gap = next - longitudes[index]!;
        if (gap > largestGap) {
            largestGap = gap;
            gapIndex = index;
        }
        yield;
    }
    let west = longitudes[(gapIndex + 1) % longitudes.length]!;
    let east = longitudes[gapIndex]!;
    if (east < west) east += fullTurn;
    if (west > fullTurn / 2) {
        west -= fullTurn;
        east -= fullTurn;
    }
    return [[west, bounds.south], [east, bounds.north]];
}

function* prepareGeometry<G extends Geometry | null | undefined>(geometry: G, bounds: PreparationBounds, flatten: boolean): Generator<void, G, unknown> {
    return yield* transformGeometrySteps(geometry, {
        visitPosition: position => extendBounds(bounds, position),
        flattenAltitude: flatten,
    });
}

function* boundsSteps(data: ViewerGeoJSON | null | undefined, wrapLongitude: boolean): Generator<void, PreparedBounds | null, unknown> {
    const bounds = createBounds(data, wrapLongitude);
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
    return yield* finishBounds(bounds);
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
    const bounds = createBounds(raw, true);
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
    return { data: { ...raw, features }, domain, snapPoints, boundsCoordinates: yield* finishBounds(bounds) };
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
