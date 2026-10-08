import type { EditableGeometry, EditableGeometryType, GeometryDraft, GeometryMeasurement, GeometryValidation, Position2D } from '../../../../../../ts-types/domain/geometry-editor.ts';
import { DEFAULTS } from '../config.ts';

const RULES = DEFAULTS.GIS_GEOMETRY;
/** Property reads precede validation in the original parser; assertions preserve that order. */
interface GeometryCandidate { type?: string; coordinates?: unknown[] | null }

const TYPES = new Set(RULES.TYPES);

function equalCoordinates(first: Position2D, second: Position2D) {
    return first[0] === second[0] && first[1] === second[1];
}

function coordinatesOf(geometry: unknown): unknown {
    if ((geometry as GeometryCandidate | null | undefined)?.type === 'LineString') return (geometry as GeometryCandidate).coordinates;
    if ((geometry as GeometryCandidate | null | undefined)?.type === 'Polygon') return (geometry as GeometryCandidate).coordinates?.[0];
    return [];
}

function validCoordinate(coordinate: unknown): coordinate is Position2D {
    return Array.isArray(coordinate) && coordinate.length === RULES.POSITION_DIMENSIONS
        && coordinate.every((value: unknown) => typeof value === 'number' && Number.isFinite(value))
        && (coordinate as Position2D)[0] >= -RULES.LONGITUDE_LIMIT && (coordinate as Position2D)[0] <= RULES.LONGITUDE_LIMIT
        && (coordinate as Position2D)[1] >= -RULES.LATITUDE_LIMIT && (coordinate as Position2D)[1] <= RULES.LATITUDE_LIMIT;
}

/** Measures coordinates only; user-provided bbox and other metadata are never trusted. */
export function measureGeometry(geometry: unknown): GeometryMeasurement {
    const positions = coordinatesOf(geometry);
    const coordinates = Array.isArray(positions) ? (positions as unknown[]).filter(validCoordinate) : [];
    let vertexCount = coordinates.length;
    if ((geometry as GeometryCandidate | null | undefined)?.type === 'Polygon' && vertexCount > 1 && equalCoordinates(coordinates[0]!, coordinates.at(-1)!)) {
        vertexCount -= 1;
    }
    if (!coordinates.length) return { areaM2: 0, areaKm2: 0, vertexCount, bounds: null };
    let west = Infinity;
    let east = -Infinity;
    let south = Infinity;
    let north = -Infinity;
    for (const [longitude, latitude] of coordinates) {
        west = Math.min(west, longitude);
        east = Math.max(east, longitude);
        south = Math.min(south, latitude);
        north = Math.max(north, latitude);
    }
    const radians = Math.PI / RULES.LONGITUDE_LIMIT;
    const areaM2 = DEFAULTS.GIS_GEOMETRY.EARTH_RADIUS_M ** 2
        * ((east - west) * radians) * 2
        * Math.cos(((north + south) / 2) * radians)
        * Math.sin(((north - south) / 2) * radians);
    return { areaM2, areaKm2: areaM2 / RULES.SQUARE_METRES_PER_SQUARE_KILOMETRE, vertexCount, bounds: [[west, south], [east, north]] };
}

function cross(first: Position2D, second: Position2D, third: Position2D) {
    return (second[0] - first[0]) * (third[1] - first[1])
        - (second[1] - first[1]) * (third[0] - first[0]);
}

function contains(first: Position2D, second: Position2D, point: Position2D) {
    return point[0] >= Math.min(first[0], second[0]) && point[0] <= Math.max(first[0], second[0])
        && point[1] >= Math.min(first[1], second[1]) && point[1] <= Math.max(first[1], second[1]);
}

function intersects(first: Position2D, second: Position2D, third: Position2D, fourth: Position2D) {
    const a = cross(first, second, third);
    const b = cross(first, second, fourth);
    const c = cross(third, fourth, first);
    const d = cross(third, fourth, second);
    if (((a > 0 && b < 0) || (a < 0 && b > 0)) && ((c > 0 && d < 0) || (c < 0 && d > 0))) return true;
    return (a === 0 && contains(first, second, third)) || (b === 0 && contains(first, second, fourth))
        || (c === 0 && contains(third, fourth, first)) || (d === 0 && contains(third, fourth, second));
}

function polygonError(coordinates: Position2D[]) {
    const vertices = coordinates.slice(0, -1);
    if (new Set(vertices.map(coordinate => coordinate.join(','))).size !== vertices.length) {
        return 'Polygon vertices must be distinct. Remove the repeated point.';
    }
    // Translate before the area sum to avoid cancellation around large GPS coordinates.
    const origin = vertices[0]!;
    let twiceArea = 0;
    for (let index = 1; index < vertices.length - 1; index += 1) {
        twiceArea += cross(origin, vertices[index]!, vertices[index + 1]!);
    }
    if (twiceArea === 0) return 'A polygon must enclose an area. Move or add a point.';
    for (let first = 0; first < vertices.length; first += 1) {
        const second = (first + 1) % vertices.length;
        for (let third = first + 1; third < vertices.length; third += 1) {
            const fourth = (third + 1) % vertices.length;
            if (first === third || second === third || fourth === first) continue;
            if (intersects(vertices[first]!, vertices[second]!, vertices[third]!, vertices[fourth]!)) {
                return 'Polygon edges cannot cross or touch. Move the crossing points.';
            }
        }
    }
    // Adjacent edges may share a vertex, but may not double back over each other.
    for (let index = 0; index < vertices.length; index += 1) {
        const previous = vertices[(index + vertices.length - 1) % vertices.length]!;
        const current = vertices[index]!;
        const next = vertices[(index + 1) % vertices.length]!;
        const overlap = (previous[0] - current[0]) * (next[0] - current[0])
            + (previous[1] - current[1]) * (next[1] - current[1]);
        if (cross(previous, current, next) === 0 && overlap > 0) {
            return 'Polygon edges cannot overlap. Move or remove the overlapping point.';
        }
    }
    return '';
}

/** Shared by the map editor and Advanced GeoJSON form. Accepts one bare geometry. */
export function validateGeometry(geometry: unknown): GeometryValidation {
    const measured = measureGeometry(geometry);
    const invalid = (error: string) => ({ ...measured, valid: false, error });
    if (!geometry || typeof geometry !== 'object' || Array.isArray(geometry) || !TYPES.has((geometry as GeometryCandidate).type!)) {
        return invalid('Use one GeoJSON LineString or Polygon geometry.');
    }
    if (Object.keys(geometry).some(key => key !== 'type' && key !== 'coordinates')) {
        return invalid('A geometry accepts only type and coordinates; remove other fields.');
    }
    if ((geometry as GeometryCandidate).type === 'Polygon' && (!Array.isArray((geometry as GeometryCandidate).coordinates) || (geometry as GeometryCandidate).coordinates!.length !== 1)) {
        return invalid('Polygons must have one outer ring and no holes.');
    }
    const coordinates = coordinatesOf(geometry) as Position2D[];
    if (!Array.isArray(coordinates) || !(coordinates as unknown[]).every(validCoordinate)) {
        return invalid(`Coordinates must be finite [longitude, latitude] pairs within −${RULES.LONGITUDE_LIMIT}…${RULES.LONGITUDE_LIMIT} and −${RULES.LATITUDE_LIMIT}…${RULES.LATITUDE_LIMIT}.`);
    }
    if ((geometry as GeometryCandidate).type === 'LineString' && coordinates.length < RULES.MIN_LINE_VERTICES) return invalid('Add at least two points to create a line.');
    if ((geometry as GeometryCandidate).type === 'Polygon' && (coordinates.length < RULES.MIN_POLYGON_VERTICES + 1 || !equalCoordinates(coordinates[0]!, coordinates.at(-1)!))) {
        return invalid('A polygon needs at least three points and a closed outer ring.');
    }
    if (measured.vertexCount > DEFAULTS.GIS_GEOMETRY.MAX_VERTICES) {
        return invalid(`A geometry can contain at most ${DEFAULTS.GIS_GEOMETRY.MAX_VERTICES} vertices.`);
    }
    for (let index = 1; index < coordinates.length; index += 1) {
        if (Math.abs(coordinates[index]![0] - coordinates[index - 1]![0]) > RULES.LONGITUDE_LIMIT) {
            return invalid(`Geometries crossing the antimeridian (±${RULES.LONGITUDE_LIMIT}° longitude) are not supported.`);
        }
        if (equalCoordinates(coordinates[index]!, coordinates[index - 1]!)) {
            return invalid('Consecutive points must have different coordinates.');
        }
    }
    if ((geometry as GeometryCandidate).type === 'Polygon') {
        const error = polygonError(coordinates);
        if (error) return invalid(error);
    }
    if (measured.areaM2 > DEFAULTS.GIS_GEOMETRY.MAX_AREA_M2) {
        return invalid(`The bounding box exceeds ${RULES.MAX_AREA_M2 / RULES.SQUARE_METRES_PER_SQUARE_KILOMETRE} km². Reduce its extent to keep the map responsive.`);
    }
    return { ...measured, valid: true, error: '' };
}

export function geometryVertices(geometry: unknown): Position2D[] {
    const positions = coordinatesOf(geometry);
    if (!Array.isArray(positions)) return [];
    const vertices = (positions as unknown[]).filter(validCoordinate).map(coordinate => [...coordinate] as Position2D);
    if ((geometry as GeometryCandidate | null | undefined)?.type === 'Polygon' && vertices.length > 1 && equalCoordinates(vertices[0]!, vertices.at(-1)!)) vertices.pop();
    return vertices;
}

export function geometryFromVertices(type: EditableGeometryType, vertices: readonly Position2D[]): EditableGeometry {
    const coordinates = vertices.map(coordinate => [...coordinate] as Position2D);
    if (type === 'Polygon') return { type, coordinates: [coordinates.length ? [...coordinates, [...coordinates[0]!]] : []] };
    return { type, coordinates };
}

/** Pure bounded draft history; callers group a drag into a single replaceVertices command. */
export function createGeometryDraft(geometry: EditableGeometry | null = null): GeometryDraft {
    return {
        type: geometry?.type || 'LineString',
        vertices: geometryVertices(geometry),
        undo: [],
        redo: [],
    };
}

export function changeDraft(draft: GeometryDraft, vertices: readonly Position2D[], type = draft.type) {
    if (JSON.stringify([draft.type, draft.vertices]) === JSON.stringify([type, vertices])) return false;
    draft.undo.push({ type: draft.type, vertices: draft.vertices.map(coordinate => [...coordinate]) });
    if (draft.undo.length > DEFAULTS.GIS_GEOMETRY.MAX_HISTORY) draft.undo.shift();
    draft.redo = [];
    draft.type = type;
    draft.vertices = vertices.map(coordinate => [...coordinate]);
    return true;
}

export function restoreDraft(draft: GeometryDraft, direction: 'undo' | 'redo') {
    const source = direction === 'undo' ? draft.undo : draft.redo;
    const target = direction === 'undo' ? draft.redo : draft.undo;
    const previous = source.pop();
    if (!previous) return false;
    target.push({ type: draft.type, vertices: draft.vertices.map(coordinate => [...coordinate]) });
    draft.type = previous.type;
    draft.vertices = previous.vertices.map(coordinate => [...coordinate]);
    return true;
}
