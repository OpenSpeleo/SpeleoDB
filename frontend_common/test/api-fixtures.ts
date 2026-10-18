import type { CylinderInstallGeoJSON, GISGeometry, GISLayer, GPSTrackWithFile, Landmark, StationTag } from '@speleodb/api';

const dates = { creation_date: '2026-01-01T00:00:00Z', modified_date: '2026-01-01T00:00:00Z' };
const permissions = { user_permission_level: 3, user_permission_level_label: 'ADMIN', can_write: true, can_delete: true };

/** Complete wire records for tests which exercise the map's stateful lifecycle. */
export function geometryFixture(overrides: Partial<GISGeometry> = {}): GISGeometry {
    return {
        id: 'g1', name: 'Boundary', alias: '', color: '#123456', description: '',
        created_by: 'tester@example.test', geometry_type: 'LineString', revision: 1,
        ...permissions, can_manage_permissions: true, ...dates,
        geojson: { type: 'LineString', coordinates: [[-87, 20], [-87.001, 20.001]] },
        bbox_area_m2: 100, vertex_count: 2, ...overrides,
    };
}

/** The shared GPS/GIS lifecycle tests need a record valid for either detail API. */
export function assetFixture(overrides: Partial<GISLayer & GPSTrackWithFile> = {}): GISLayer & GPSTrackWithFile {
    return {
        id: 'item', name: 'Survey', description: '', color: '#123456',
        created_by: 'tester@example.test', file: '/track', source_format: 'GPX',
        ...permissions, can_manage_permissions: true, ...dates, ...overrides,
    };
}

export function tagFixture(overrides: Partial<StationTag> = {}): StationTag {
    return { id: 'tag-1', name: 'Important', color: '#ff0000', user: 1, station_count: 0, ...dates, ...overrides };
}

export function landmarkFixture(overrides: Partial<Landmark> = {}): Landmark {
    return {
        id: 'landmark-1', name: 'Entrance', description: '', icon: 'DEFAULT',
        collection: null, collection_name: null, collection_color: null,
        can_write: true, can_delete: true, latitude: 20, longitude: -87,
        created_by: 'tester@example.test', ...dates, ...overrides,
    };
}

export function cylinderInstallFixture(): CylinderInstallGeoJSON {
    return {
        id: 'cylinder', type: 'Feature', geometry: { type: 'Point', coordinates: [-87, 20] },
        properties: {
            id: 'cylinder', cylinder_id: 'c1', cylinder_name: 'Cylinder', cylinder_serial: 'serial',
            fleet_id: 'f1', fleet_name: 'Fleet', project_id: 'p1', project_name: 'Project',
            location_name: 'Entrance', install_date: null, install_user: 'tester@example.test',
            distance_from_entry: null, unit_system: 'METRIC', status: 'INSTALLED',
            o2_percentage: 21, he_percentage: 0, pressure: 200, pressure_unit_system: 'METRIC',
        },
    };
}
