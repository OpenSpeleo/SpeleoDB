import { DEFAULTS } from '../config.js';
import { calculateDistanceInMeters } from '../map/geodesy.js';

const settings = DEFAULTS.MEASUREMENT;
const halfTurn = DEFAULTS.GEODESY.DEGREES_PER_HALF_TURN;
const radians = Math.PI / halfTurn;

export function createMeasurement(start, end, id) {
    return { id, start: [...start], end: [...end], distanceMeters: calculateDistanceInMeters(start, end) };
}

function displayValue(value, decimals, unit) {
    const resolution = 10 ** -decimals;
    if (value > 0 && value < resolution) return `<${resolution} ${unit}`;
    return `${Number(value.toFixed(decimals))} ${unit}`;
}

export function formatDistance(meters) {
    const value = Math.max(0, meters);
    const feet = value / settings.METERS_PER_FOOT;
    const metric = Number(value.toFixed(settings.METER_DECIMALS)) >= settings.METERS_PER_KILOMETER
        ? displayValue(value / settings.METERS_PER_KILOMETER, settings.LARGE_UNIT_DECIMALS, 'km')
        : displayValue(value, settings.METER_DECIMALS, 'm');
    const imperial = Math.round(feet) >= settings.FEET_PER_MILE
        ? displayValue(feet / settings.FEET_PER_MILE, settings.LARGE_UNIT_DECIMALS, 'mi')
        : displayValue(feet, 0, 'ft');
    return { metric, imperial, label: `${metric} · ${imperial}` };
}

function wrapLongitude(longitude) {
    const turn = halfTurn * 2;
    return ((longitude + halfTurn) % turn + turn) % turn - halfTurn;
}

/** Reject sky/horizon clamping as well as locations outside native render limits. */
export function coordinateFromPoint(map, point) {
    if (!point || !Number.isFinite(point.x) || !Number.isFinite(point.y)) return null;
    if (map.isPointOnSurface && !map.isPointOnSurface(point)) return null;
    const coordinate = map.unproject(point);
    if (!coordinate || !Number.isFinite(coordinate.lng) || !Number.isFinite(coordinate.lat)
        || Math.abs(coordinate.lat) > settings.MAX_LATITUDE) return null;
    const projected = map.project(coordinate);
    if (!projected || !Number.isFinite(projected.x) || !Number.isFinite(projected.y)
        || Math.hypot(projected.x - point.x, projected.y - point.y)
            > settings.SURFACE_ROUNDTRIP_TOLERANCE_PX) return null;
    return [wrapLongitude(coordinate.lng), coordinate.lat];
}

function vector([longitude, latitude]) {
    const cosLatitude = Math.cos(latitude * radians);
    return [cosLatitude * Math.cos(longitude * radians), cosLatitude * Math.sin(longitude * radians), Math.sin(latitude * radians)];
}

function cross(a, b) {
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
}

function normalize(value) {
    const length = Math.hypot(...value);
    return value.map(component => component / length);
}

/** Sample a geographic decorative arc; endpoints and measured distance stay exact. */
export function sampleCurve(start, end) {
    const a = vector(start);
    const b = vector(end);
    let normal = cross(a, b);
    const crossLength = Math.hypot(...normal);
    const angle = Math.atan2(crossLength, a.reduce((sum, value, index) => sum + value * b[index], 0));
    if (angle < settings.VECTOR_EPSILON) return [[...start], [...end]];
    if (crossLength < settings.VECTOR_EPSILON) {
        // Choose the least parallel axis to make exact antipodes deterministic.
        const axisIndex = a.reduce((best, value, index) => Math.abs(value) < Math.abs(a[best]) ? index : best, 0);
        normal = cross(a, [0, 1, 2].map(index => Number(index === axisIndex)));
    }
    normal = normalize(normal);
    const tangent = cross(normal, a);
    const count = Math.max(settings.MIN_CURVE_SEGMENTS, Math.min(settings.MAX_CURVE_SEGMENTS,
        Math.ceil(angle / radians / settings.CURVE_STEP_DEGREES)));
    const amplitude = Math.min(settings.CURVE_OFFSET_RATIO * angle, settings.MAX_CURVE_OFFSET_RADIANS);
    return Array.from({ length: count + 1 }, (_, index) => {
        if (index === 0) return [...start];
        if (index === count) return [...end];
        const fraction = index / count;
        const offset = Math.sin(Math.PI * fraction) * amplitude;
        const arc = a.map((component, axis) => component * Math.cos(fraction * angle) + tangent[axis] * Math.sin(fraction * angle));
        const bent = normalize(arc.map((component, axis) => component * Math.cos(offset) + normal[axis] * Math.sin(offset)));
        return [Math.atan2(bent[1], bent[0]) / radians, Math.asin(Math.max(-1, Math.min(1, bent[2]))) / radians];
    });
}

function interpolate(a, b, fraction) {
    return a.map((value, axis) => value + (b[axis] - value) * fraction);
}

/** Clip at the native polar cap and split at the date line, never drawing across a world. */
export function curveLineParts(samples) {
    const parts = [];
    let part = [];
    const flush = () => {
        if (part.length > 1) parts.push(part);
        part = [];
    };
    for (let index = 1; index < samples.length; index++) {
        let a = [...samples[index - 1]];
        let b = [...samples[index]];
        if (b[0] - a[0] > halfTurn) b[0] -= halfTurn * 2;
        if (b[0] - a[0] < -halfTurn) b[0] += halfTurn * 2;
        const aVisible = Math.abs(a[1]) <= settings.MAX_LATITUDE;
        const bVisible = Math.abs(b[1]) <= settings.MAX_LATITUDE;
        if (!aVisible && !bVisible) { flush(); continue; }
        if (!aVisible) a = interpolate(a, b, (Math.sign(a[1]) * settings.MAX_LATITUDE - a[1]) / (b[1] - a[1]));
        if (!bVisible) b = interpolate(a, b, (Math.sign(b[1]) * settings.MAX_LATITUDE - a[1]) / (b[1] - a[1]));
        const longitudeShift = wrapLongitude(a[0]) - a[0];
        a[0] += longitudeShift;
        b[0] += longitudeShift;
        if (part.length && Math.abs(part.at(-1)[0] - a[0]) > halfTurn) flush();
        if (!part.length) part.push(a);
        if (b[0] > halfTurn || b[0] < -halfTurn) {
            const boundary = Math.sign(b[0]) * halfTurn;
            const crossing = interpolate(a, b, (boundary - a[0]) / (b[0] - a[0]));
            part.push(crossing);
            flush();
            part.push([-boundary, crossing[1]]);
            b[0] -= Math.sign(b[0]) * halfTurn * 2;
        }
        part.push(b);
        if (!bVisible) flush();
    }
    flush();
    return parts;
}

export function measurementFeatures(measurement, priority = 0) {
    const properties = { measurementId: measurement.id, priority };
    const features = [{ type: 'Feature', properties: { ...properties, role: 'endpoint' }, geometry: { type: 'Point', coordinates: measurement.start } }];
    if (!measurement.end) return features;
    features.push({ type: 'Feature', properties: { ...properties, role: 'endpoint' }, geometry: { type: 'Point', coordinates: measurement.end } });
    const samples = sampleCurve(measurement.start, measurement.end);
    const parts = curveLineParts(samples);
    if (parts.length) features.push({ type: 'Feature', properties: { ...properties, role: 'line' }, geometry: { type: 'MultiLineString', coordinates: parts } });
    const middle = samples[Math.floor(samples.length / 2)];
    // A valid polar measurement still needs a result when its arc crosses the cap.
    const labelPosition = Math.abs(middle[1]) <= settings.MAX_LATITUDE ? middle : measurement.start;
    features.push({
        type: 'Feature', properties: { ...properties, role: 'label', label: formatDistance(measurement.distanceMeters).label },
        geometry: { type: 'Point', coordinates: labelPosition },
    });
    return features;
}
