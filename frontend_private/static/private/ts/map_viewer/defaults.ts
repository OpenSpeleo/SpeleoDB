import { FEET_TO_METERS } from '@speleodb/map-core/depth';
import { GEOJSON_LINE_RENDER_DEFAULTS } from '@speleodb/map-viewer/expressions';
import type { DisplayCategory, DisplayStationType } from '../../../../../ts-types/domain/map-display.ts';
import geometryContract from '@speleodb/map-core/geometry-contract.json' with { type: 'json' };

// ============================================================
// DEFAULTS — single source of truth for every tuneable constant
// in the map viewer. No magic numbers anywhere else.
// ============================================================
export const DEFAULTS = Object.freeze({
    VIEWER_WORK: {
        BUDGET_MS: 8,
        WORKER_PARSE_BYTES: 4 * 1024 * 1024,
        WORKER_NODE_BATCH_SIZE: 1000,
    },
    MAP: {
        STYLE: 'mapbox://styles/mapbox/satellite-streets-v12',
        DEFAULT_SOURCE_ID: 'mapbox-satellite',
        RASTER_GLYPHS: 'https://fonts.openmaptiles.org/{fontstack}/{range}.pbf',
        CENTER: [2.35, 46.6],
        INITIAL_ZOOM: 0,
        LIMITED_MAX_ZOOM: 13,
        PRECISE_MAX_ZOOM: 22,
        FLY_TO_ZOOM: 18,
        FIT_BOUNDS_PADDING: 50,
        FIT_BOUNDS_MAX_ZOOM: 16,
        ANTIMERIDIAN_WRAP_DEGREES: 360,
        SCALE_CONTROL_MAX_WIDTH: 200,
        RESIZE_DELAY_MS: 100,
        MISSING_TILE_SHA256_HASHES: Object.freeze([
            '9eafd300d61393184a4abc1d458564cfd1cd9b6f9c4e9c74687045c0a0e5b858',
        ]),
    },

    DEPTH: {
        LIMIT_FEET: null,
        UNIT: 'ft',
        INPUT_SIGNIFICANT_DIGITS: 12,
        DISPLAY_DECIMALS: 1,
        ZERO_DOMAIN_MAX_FEET: 1e-9,
        HOVER_QUERY_PADDING_PX: 12,
    },

    GEODESY: {
        EARTH_RADIUS_METERS: 6_371_000,
        DEGREES_PER_HALF_TURN: 180,
    },

    MEASUREMENT: {
        LAYER_PREFIX: 'speleo-measurement-',
        LAYER_ROLES: ['completed-casing', 'completed-line', 'completed-endpoints', 'completed-label',
            'draft-casing', 'draft-line', 'draft-endpoints'],
        COMPACT_HEIGHT_PX: 340,
        PANEL_GAP_PX: 12,
        MIN_INSTRUCTION_WIDTH_PX: 180,
        MAX_LATITUDE: 85.051129,
        SURFACE_ROUNDTRIP_TOLERANCE_PX: 1,
        VECTOR_EPSILON: 1e-10,
        CURVE_OFFSET_RATIO: 0.06,
        MAX_CURVE_OFFSET_RADIANS: 0.01,
        CURVE_STEP_DEGREES: 1,
        MIN_CURVE_SEGMENTS: 32,
        MAX_CURVE_SEGMENTS: 256,
        METERS_PER_KILOMETER: 1000,
        METERS_PER_FOOT: FEET_TO_METERS,
        FEET_PER_MILE: 5280,
        METER_DECIMALS: 1,
        LARGE_UNIT_DECIMALS: 2,
        LINE_COLOR: '#7dd3fc',
        CASING_COLOR: '#0f172a',
        LINE_WIDTH: 2,
        CASING_WIDTH: 5,
        CASING_OVERVIEW_WIDTH_OFFSET: 1,
        DRAFT_DASH_ARRAY: [2, 2],
        ENDPOINT_RADIUS: 4,
        ENDPOINT_STROKE_WIDTH: 2,
        LABEL_TEXT_COLOR: '#f8fafc',
        LIVE_LABEL_OCCLUDED_OPACITY: 0,
        LABEL_BACKGROUND_RGBA: [15, 23, 42, 242],
        LABEL_BORDER_RGBA: [71, 85, 105, 255],
        LABEL_IMAGE_SIZE: 32,
        LABEL_IMAGE_RADIUS: 10,
        LABEL_IMAGE_BORDER_WIDTH: 1,
        LABEL_TEXT_SIZE: 13,
        LABEL_PADDING: [6, 10, 6, 10],
        LABEL_COLLISION_PADDING: 8,
        LABEL_ANCHORS: ['center', 'top', 'bottom', 'left', 'right'],
        LABEL_FONTS: ['Open Sans Semibold', 'Arial Unicode MS Regular'],
    },

    // Keep short lines; simplification can discard whole features.
    GEOJSON_RENDER: GEOJSON_LINE_RENDER_DEFAULTS,

    PROJECT_RENDER: {
        DETAIL_WIDTH: 5,
        CLOSE_WIDTH: 6,
    },

    GPS_TRACK_RENDER: {
        DETAIL_WIDTH: 6,
        CLOSE_WIDTH: 7,
    },

    ZOOM_LEVELS: {
        PROJECT_LINE: 0,
        PROJECT_LINE_LABEL: 14,
        PROJECT_ENTRY_SYMBOL: 10,
        LANDMARK_SYMBOL: 12,
        LANDMARK_LABEL: 16,
        SURFACE_STATION_SYMBOL: 12,
        SURFACE_STATION_LABEL: 16,
        SUBSURFACE_STATION_SYMBOL: 12,
        SUBSURFACE_STATION_LABEL: 16,
        CYLINDER_INSTALL_SYMBOL: 12,
        CYLINDER_INSTALL_LABEL: 16,
        EXPLORATION_LEAD_SYMBOL: 12,
        GPS_TRACK_LINE: 0,
    },

    SNAP: {
        RADIUS_METERS: 10,
        MIN_RADIUS: 1,
    },

    DRAG: {
        THRESHOLD_PX: 10,
        QUERY_PADDING_PX: 8,
    },

    UI: {
        MODAL_SETUP_DELAY_MS: 50,
        MOBILE_BREAKPOINT: 640,
        MIN_MAP_HEIGHT: 600,
        MAP_PADDING_OFFSET: 20,
        NOTIFICATION_DURATION_MS: 3000,
        NOTIFICATION_FADEOUT_MS: 300,
        OVERLAY_FADE_DELAY_MS: 500,
        TRACK_NAME_MAX_LENGTH: 30,
        GIS_LAYER_NAME_MAX_LENGTH: 30,
        NOTE_PREVIEW_LENGTH: 200,
        COUNTRY_GROUP_TRANSITION_MS: 250,
        MAP_PANEL_EDGE_PX: 16,
        MAP_PANEL_GAP_PX: 10,
        MAP_PANEL_POSITION_DELAY_MS: 50,
    },

    GIS_LAYER_RENDER: {
        FILL_OPACITY: 0.35,
        OUTLINE_WIDTH: 1.5,
        LINE_WIDTH: 2.5,
        LINE_OPACITY: 0.95,
        POINT_RADIUS_ZOOM_MIN: 5,
        POINT_RADIUS_MIN: 3,
        POINT_RADIUS_ZOOM_MAX: 14,
        POINT_RADIUS_MAX: 6,
        POINT_STROKE_COLOR: '#ffffff',
        POINT_STROKE_WIDTH: 1,
        POPUP_MAX_WIDTH_PX: 360,
        POPUP_DESCRIPTION_MAX_CHARS: 1200,
        POPUP_METADATA_MAX_ROWS: 4,
        POPUP_METADATA_VALUE_MAX_CHARS: 180,
        POPUP_OVERFLOW_TOLERANCE_PX: 1,
        POPUP_SCROLL_THUMB_MIN_PX: 28,
    },

    GIS_GEOMETRY: {
        DRAFT_LAYER_PREFIX: 'gis-geometry-draft-',
        DRAFT_LAYER_ROLES: ['fill', 'line', 'bbox', 'midpoints', 'vertices'],
        TYPES: Object.freeze(geometryContract.types),
        NAME_MAX_LENGTH: geometryContract.name_max_length,
        POSITION_DIMENSIONS: geometryContract.position_dimensions,
        MIN_LINE_VERTICES: geometryContract.min_line_vertices,
        MIN_POLYGON_VERTICES: geometryContract.min_polygon_vertices,
        LONGITUDE_LIMIT: geometryContract.longitude_limit,
        LATITUDE_LIMIT: geometryContract.latitude_limit,
        SQUARE_METRES_PER_SQUARE_KILOMETRE: geometryContract.square_metres_per_square_kilometre,
        BBOX_DASH_ARRAY: [3, 3],
        MAX_VERTICES: geometryContract.max_vertices,
        MAX_AREA_M2: geometryContract.max_area_m2,
        WARNING_AREA_M2: geometryContract.warning_area_m2,
        EARTH_RADIUS_M: geometryContract.earth_radius_m,
        COORDINATE_PRECISION: 6,
        AREA_DISPLAY_PRECISION: 4,
        FIT_MARGIN_RATIO: 0.1,
        MOBILE_EDGE_PX: 10,
        MOBILE_VISIBLE_HEIGHT_RATIO: 0.75,
        MAX_HISTORY: 100,
        VERTEX_RADIUS: 6,
        SELECTED_VERTEX_RADIUS: 8,
        VERTEX_STROKE_WIDTH: 2,
        MIDPOINT_RADIUS: 4,
        LINE_WIDTH: 3,
        FILL_OPACITY: 0.175,
        DRAFT_FILL_OPACITY: 0.09,
        BBOX_LINE_WIDTH: 1,
        HANDLE_QUERY_PADDING: 10,
        DRAG_THRESHOLD: 4,
        COLORS: {
            HANDLE: '#ffffff', SELECTED: '#38bdf8', WARNING: '#f59e0b',
            INVALID: '#ef4444', BBOX: '#94a3b8',
        },
    },

    UPLOAD: {
        MAX_FILE_SIZE: 500 * 1024 * 1024,
    },

    CSRF: {
        SECRET_LENGTH: 32,
        TOKEN_LENGTH: 64,
    },

    COLORS: {
        DEFAULT_STATION: '#fb923c',
        FALLBACK: '#94a3b8',
        DEPTH_NONE: '#999999',
        DEPTH_SHALLOW: '#4575b4',
        DEPTH_MID: '#e6f598',
        DEPTH_DEEP: '#d73027',
    },

    DISPLAY: {
        COLOR_MODE: 'project',
        COLOR_MODES: Object.freeze(['project', 'depth', 'shot']),
        STORAGE_VERSION: 1,
        CATEGORIES: Object.freeze([
            { id: 'caveEntrances', label: 'Cave entrances' },
            { id: 'surveyStations', label: 'Survey stations' },
            { id: 'surfaceStations', label: 'Surface stations' },
            { id: 'landmarks', label: 'Landmarks' },
            { id: 'explorationLeads', label: 'Exploration leads' },
            { id: 'cylinders', label: 'Safety cylinders' },
        ].map(Object.freeze) as Readonly<{ id: DisplayCategory; label: string }>[]),
        // Presentation and rendering metadata for SubSurfaceStationType.
        // Missing/null legacy feature types use the Sensor entry.
        STATION_TYPES: Object.freeze([
            { id: 'sensor', label: 'Sensor', layerSuffix: 'circles' },
            { id: 'biology', label: 'Biology', layerSuffix: 'biology-icons' },
            { id: 'bone', label: 'Bones', layerSuffix: 'bone-icons' },
            { id: 'artifact', label: 'Artifact', layerSuffix: 'artifact-icons' },
            { id: 'geology', label: 'Geology', layerSuffix: 'geology-icons' },
        ].map(Object.freeze) as Readonly<{ id: DisplayStationType; label: string; layerSuffix: string }>[]),
    },

    STORAGE_KEYS: {
        DISPLAY_PREFERENCES: 'speleo_private_map_display',
        PROJECT_VISIBILITY: 'speleo_project_visibility',
        NETWORK_VISIBILITY: 'speleo_network_visibility',
        COUNTRY_COLLAPSED: 'speleo_country_collapsed',
        COUNTRY_VISIBILITY: 'speleo_country_visibility',
        MAP_SOURCE: 'speleo_map_source',
        PROJECTS_COUNTRY_COLLAPSED: 'speleo_projects_collapsed_countries', // used by projects.html inline JS
    },
});
