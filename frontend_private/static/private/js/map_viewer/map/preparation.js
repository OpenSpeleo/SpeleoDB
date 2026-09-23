import { DEFAULTS } from '../config.js';
import { DepthUtils, resolveLineDepthValue } from './depth.js';
import { GEOMETRY_TYPES, GIS_GEOMETRY_TYPE_PROPERTY } from './gis_layer_geometry.js';

// Parallel downloads can resume in the same task. They share a CPU allowance
// instead of each starting another full slice before the browser gets a turn.
let preparationSliceStarted = null;

/** Run CPU work in bounded tasks, including within one large geometry. */
async function runPreparation(steps, {
    isCurrent = () => true,
    yieldWork = () => new Promise(resolve => setTimeout(resolve, 0)),
    budgetMs = DEFAULTS.VIEWER_WORK.BUDGET_MS,
} = {}) {
    const assertCurrent = () => {
        if (!isCurrent()) throw new DOMException('Viewer preparation superseded', 'AbortError');
    };
    assertCurrent();
    await yieldWork();
    assertCurrent();
    const started = performance.now();
    if (preparationSliceStarted === null || started < preparationSliceStarted) preparationSliceStarted = started;
    for (;;) {
        const step = steps.next();
        if (step.done) {
            assertCurrent();
            return step.value;
        }
        if (performance.now() - preparationSliceStarted >= budgetMs) {
            assertCurrent();
            await yieldWork();
            assertCurrent();
            preparationSliceStarted = performance.now();
        }
    }
}

function readBBox(data) {
    const bbox = data?.bbox;
    if (!Array.isArray(bbox) || bbox.length < 4 || bbox.length % 2 || !bbox.every(Number.isFinite)) return null;
    const dimensions = bbox.length / 2;
    const west = bbox[0];
    const east = bbox[dimensions] < west ? bbox[dimensions] + DEFAULTS.MAP.ANTIMERIDIAN_WRAP_DEGREES : bbox[dimensions];
    return [[west, bbox[1]], [east, bbox[dimensions + 1]]];
}

function createBounds(data, wrapLongitude) {
    return {
        bbox: readBBox(data), wrapLongitude, longitudes: [],
        west: Infinity, east: -Infinity, south: Infinity, north: -Infinity,
    };
}

function extendBounds(bounds, coordinates) {
    if (bounds.bbox) return;
    const [longitude, latitude] = coordinates;
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
function* sortLongitudes(values) {
    let sorted = values;
    let scratch = new Array(values.length);
    for (let width = 1; width < values.length; width *= 2) {
        for (let start = 0; start < values.length; start += width * 2) {
            const middle = Math.min(start + width, values.length);
            const end = Math.min(start + width * 2, values.length);
            let left = start;
            let right = middle;
            for (let out = start; out < end; out += 1) {
                scratch[out] = left < middle && (right >= end || sorted[left] <= sorted[right])
                    ? sorted[left++] : sorted[right++];
                yield;
            }
        }
        [sorted, scratch] = [scratch, sorted];
    }
    return sorted;
}

function* finishBounds(bounds) {
    if (bounds.bbox) return bounds.bbox;
    if (!Number.isFinite(bounds.south)) return null;
    if (!bounds.wrapLongitude) return [[bounds.west, bounds.south], [bounds.east, bounds.north]];
    const longitudes = yield* sortLongitudes(bounds.longitudes);
    const fullTurn = DEFAULTS.MAP.ANTIMERIDIAN_WRAP_DEGREES;
    let largestGap = -Infinity;
    let gapIndex = 0;
    for (let index = 0; index < longitudes.length; index += 1) {
        const next = index === longitudes.length - 1 ? longitudes[0] + fullTurn : longitudes[index + 1];
        const gap = next - longitudes[index];
        if (gap > largestGap) {
            largestGap = gap;
            gapIndex = index;
        }
        yield;
    }
    let west = longitudes[(gapIndex + 1) % longitudes.length];
    let east = longitudes[gapIndex];
    if (east < west) east += fullTurn;
    if (west > fullTurn / 2) {
        west -= fullTurn;
        east -= fullTurn;
    }
    return [[west, bounds.south], [east, bounds.north]];
}

function* prepareCoordinates(coordinates, bounds, flatten) {
    if (!Array.isArray(coordinates) || !coordinates.length) return coordinates;
    if (typeof coordinates[0] === 'number') {
        extendBounds(bounds, coordinates);
        yield;
        return flatten && coordinates.length >= 3 ? [coordinates[0], coordinates[1], 0] : coordinates;
    }
    const output = flatten ? [] : coordinates;
    for (const child of coordinates) {
        const prepared = yield* prepareCoordinates(child, bounds, flatten);
        if (flatten) output.push(prepared);
        yield;
    }
    return output;
}

function* prepareGeometry(geometry, bounds, flatten) {
    if (!geometry) return geometry;
    if (geometry.type === 'GeometryCollection') {
        const geometries = [];
        for (const child of geometry.geometries || []) {
            const prepared = yield* prepareGeometry(child, bounds, flatten);
            if (flatten) geometries.push(prepared);
            yield;
        }
        return flatten ? { ...geometry, geometries } : geometry;
    }
    const coordinates = yield* prepareCoordinates(geometry.coordinates, bounds, flatten);
    return flatten ? { ...geometry, coordinates } : geometry;
}

function* boundsSteps(data, wrapLongitude) {
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
export function prepareGeoJSONBounds(data, { wrapLongitude = true, ...options } = {}) {
    return runPreparation(boundsSteps(data, wrapLongitude), options);
}

function* projectSteps(raw) {
    if (!Array.isArray(raw?.features)) return { data: raw, domain: null, snapPoints: [], boundsCoordinates: null };
    const sections = new Map();
    for (const feature of raw.features) {
        if (feature?.geometry?.type === 'Point') {
            const section = DepthUtils.getFeatureSectionName(feature.properties);
            const depth = DepthUtils.getFeatureDepthValue(feature.properties);
            if (section != null && Number.isFinite(depth)) {
                const entry = sections.get(section) || { sum: 0, count: 0 };
                entry.sum += depth;
                entry.count += 1;
                sections.set(section, entry);
            }
        }
        yield;
    }
    const averages = new Map();
    let maximum = -Infinity;
    for (const [section, { sum, count }] of sections) {
        const average = sum / count;
        averages.set(section, average);
        if (Number.isFinite(average)) maximum = Math.max(maximum, average);
        yield;
    }
    for (const feature of raw.features) {
        if (feature?.geometry?.type === 'LineString') {
            const depth = resolveLineDepthValue(feature.properties, averages);
            if (Number.isFinite(depth)) maximum = Math.max(maximum, depth);
        }
        yield;
    }
    const domain = Number.isFinite(maximum) ? { min: 0, max: Math.max(0, maximum) } : null;
    const denominator = domain ? Math.max(DEFAULTS.DEPTH.ZERO_DOMAIN_MAX_FEET, domain.max) : 1;
    const bounds = createBounds(raw, true);
    const features = [];
    const snapPoints = [];
    for (let index = 0; index < raw.features.length; index += 1) {
        const original = raw.features[index];
        if (!original) {
            features.push(original);
            yield;
            continue;
        }
        const feature = { ...original, geometry: yield* prepareGeometry(original.geometry, bounds, true) };
        if (feature.geometry?.type === 'LineString') {
            if (feature.properties) {
                feature.properties = { ...feature.properties };
                const depth = resolveLineDepthValue(feature.properties, averages);
                if (Number.isFinite(depth)) {
                    feature.properties.depth_val = depth;
                    feature.properties.depth_norm = Math.min(Math.max(depth / denominator, 0), 1);
                } else {
                    delete feature.properties.depth_val;
                    delete feature.properties.depth_norm;
                }
            }
            const coords = feature.geometry.coordinates;
            if (coords?.length >= 2) {
                const lineName = feature.properties?.section_name || feature.properties?.name || `Line ${index}`;
                snapPoints.push(
                    { coordinates: [coords[0][0], coords[0][1]], lineName, type: 'start', lineIndex: 0 },
                    { coordinates: [coords.at(-1)[0], coords.at(-1)[1]], lineName, type: 'end', lineIndex: coords.length - 1 },
                );
            }
        }
        features.push(feature);
        yield;
    }
    return { data: { ...raw, features }, domain, snapPoints, boundsCoordinates: yield* finishBounds(bounds) };
}

/** Immutable preparation; callers publish the complete result only if still current. */
export function prepareProjectGeoJSON(data, options) {
    return runPreparation(projectSteps(data), options);
}

function* gisSteps(geojson) {
    const features = [];
    const found = new Set();
    function* append(geometry, feature) {
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
        data: { type: 'FeatureCollection', features },
        geometryTypes: GEOMETRY_TYPES.filter(type => found.has(type)),
    };
}

/** GIS display annotations preserve cached coordinates and yield per feature. */
export function prepareGISLayerGeoJSONAsync(data, options) {
    return runPreparation(gisSteps(data), options);
}
