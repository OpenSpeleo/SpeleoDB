import type { EntityId } from '../../../../../ts-types/domain/identifiers.ts';
import type { ViewerProject, ViewerNetwork, ViewerGPSTrack, ViewerGISLayer, GISGeometryMetadata, GISGeometryResponse, ProjectResponse, PermissionAction as Action, StationScopeRecord, LoadOverlayOptions } from '../../../../../ts-types/domain/map-config.ts';
import { API } from './api.ts';
import { DEFAULTS } from './defaults.ts';

export { DEFAULTS } from './defaults.ts';

export const MAP_SOURCES = Object.freeze([
    Object.freeze({
        id: 'mapbox-satellite',
        label: 'MapBox - Satellite',
        type: 'mapbox-style',
        style: DEFAULTS.MAP.STYLE,
        requiresToken: true,
    }),
    Object.freeze({
        id: 'esri-satellite',
        label: 'ESRI - Satellite',
        type: 'raster',
        tiles: [
            'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
        ],
        tileSize: 256,
        maxzoom: 18,
        attribution: 'Sources: Esri, USGS, NOAA',
        requiresToken: false,
    }),
    Object.freeze({
        id: 'esri-world-hillshade',
        label: 'ESRI - World Hillshade',
        type: 'raster',
        tiles: [
            'https://services.arcgisonline.com/arcgis/rest/services/Elevation/World_Hillshade/MapServer/tile/{z}/{y}/{x}'
        ],
        tileSize: 256,
        maxzoom: 16,
        attribution: 'Sources: Esri, USGS, NOAA',
        requiresToken: false,
    }),
    Object.freeze({
        id: 'esri-world-hillshade-dark',
        label: 'ESRI - World Hillshade Dark',
        type: 'raster',
        tiles: [
            'https://server.arcgisonline.com/ArcGIS/rest/services/Elevation/World_Hillshade_Dark/MapServer/tile/{z}/{y}/{x}'
        ],
        tileSize: 256,
        maxzoom: 16,
        attribution: 'Sources: Esri, USGS, NOAA',
        requiresToken: false,
    }),
]);

const PermissionAction = Object.freeze({
    READ: 'read',
    WRITE: 'write',
    DELETE: 'delete',
});

const ProjectPermissionRank = Object.freeze({
    UNKNOWN: 0,
    WEB_VIEWER: 1,
    READ_ONLY: 2,
    READ_AND_WRITE: 3,
    ADMIN: 4,
});

const ProjectActionMinRank = Object.freeze({
    [PermissionAction.READ]: ProjectPermissionRank.READ_ONLY,
    [PermissionAction.WRITE]: ProjectPermissionRank.READ_AND_WRITE,
    [PermissionAction.DELETE]: ProjectPermissionRank.ADMIN,
});

const NetworkActionMinLevel = Object.freeze({
    [PermissionAction.READ]: 1,
    [PermissionAction.WRITE]: 2,
    [PermissionAction.DELETE]: 3,
});

export const Config = {
    // Private storage for projects loaded from API
    _projects: null as ViewerProject[] | null,

    // Private storage for networks loaded from API
    _networks: null as ViewerNetwork[] | null,

    // Private storage for GPS tracks loaded from API
    _gpsTracks: null as ViewerGPSTrack[] | null,

    // Private storage for GIS Layers loaded from API
    _gisLayers: null as ViewerGISLayer[] | null,
    _gisGeometries: null as GISGeometryMetadata[] | null,
    gisGeometriesError: false,

    get gisGeometries() {
        return this._gisGeometries || [];
    },

    getGISGeometryById(id: EntityId | null | undefined) {
        return this.gisGeometries.find(geometry => geometry.id === String(id)) || null;
    },

    upsertGISGeometry(record: GISGeometryResponse) {
        // Metadata stays in Config; coordinate payloads belong to State's cache.
        const { geojson: _geojson, ...metadata } = record;
        const existing = this.getGISGeometryById(record.id);
        if (existing && existing.revision > record.revision) return;
        this._gisGeometries ??= [];
        if (existing) Object.assign(existing, metadata, { id: String(record.id) });
        else this._gisGeometries.push({ ...metadata, id: String(record.id) });
    },

    hasGISGeometryAccess(id: EntityId | null | undefined, action: unknown = PermissionAction.READ) {
        const geometry = this.getGISGeometryById(id);
        if (!geometry) return false;
        if (action === PermissionAction.READ) return true;
        if (action === PermissionAction.WRITE) return geometry.can_write === true;
        if (action === PermissionAction.DELETE) return geometry.can_delete === true;
        return false;
    },

    async loadGISGeometries() {
        if (this._gisGeometries && !this.gisGeometriesError) return this._gisGeometries;
        const revisions = new Map(this.gisGeometries.map(record => [record.id, record.revision]));
        try {
            const response = await API.getGISGeometries();
            const records = Array.isArray(response) ? response : [];
            const returnedIds = new Set(records.map(record => String(record.id)));
            // A retry can overlap a successful local save. Retain returned rows
            // for revision-aware merging and records changed during this request.
            this._gisGeometries = this.gisGeometries.filter(record =>
                returnedIds.has(record.id) || !revisions.has(record.id)
                || revisions.get(record.id) !== record.revision);
            records.forEach(record => this.upsertGISGeometry(record));
            this.gisGeometriesError = false;
        } catch (error) {
            console.error('Failed to load GIS Geometries:', error);
            this.gisGeometriesError = true;
        }
        return this.gisGeometries;
    },

    get projects() {
        return this._projects || [];
    },

    get projectIds() {
        return this.projects.map(p => p.id);
    },

    get networks() {
        return this._networks || [];
    },

    get networkIds() {
        return this.networks.map(n => n.id);
    },

    get gpsTracks() {
        return this._gpsTracks || [];
    },

    get gpsTrackIds() {
        return this.gpsTracks.map(t => t.id);
    },

    get gisLayers() {
        return this._gisLayers || [];
    },

    get gisLayerIds() {
        return this.gisLayers.map(layer => layer.id);
    },

    setPublicProjects(projects: ProjectResponse[]) {
        this._projects = projects.map(p => ({
            id: String(p.id),
            name: p.name,
            color: p.color,
            permissions: 'READ_ONLY',
            geojson_url: p.geojson_url || p.geojson_file,
        }));
    },

    async loadProjects() {
        if (this._projects) {
            return this._projects;
        }

        try {
            console.log('🔄 Loading projects from API...');
            const response = await API.getAllProjects();

            if (Array.isArray(response)) {
                this._projects = response.map(p => ({
                    id: String(p.id),
                    name: p.name,
                    permissions: p.permission,  // API returns 'permission', code expects 'permissions'
                    description: p.description,
                    country: p.country,
                    color: p.color,
                    latitude: p.latitude,
                    longitude: p.longitude,
                    visibility: p.visibility,
                    geojson_url: p.geojson_url,  // If available
                }));
                console.log(`✅ Loaded ${this._projects.length} projects from API`);
            } else {
                console.error('❌ Invalid projects response:', response);
                this._projects = [];
            }
        } catch (error) {
            console.error('❌ Failed to load projects from API:', error);
            this._projects = [];
        }

        return this._projects;
    },

    // Load networks from API (call this early in initialization)
    async loadNetworks() {
        if (this._networks) {
            return this._networks;
        }

        try {
            console.log('🔄 Loading surface networks from API...');
            const response = await API.getAllSurfaceNetworks();

            if (Array.isArray(response)) {
                this._networks = response.map(n => ({
                    id: String(n.id),
                    name: n.name,
                    description: n.description,
                    is_active: n.is_active,
                    created_by: n.created_by,
                    creation_date: n.creation_date,
                    modified_date: n.modified_date,
                    permissions: n.user_permission_level_label,  // API returns permission label
                    permission_level: n.user_permission_level,   // Numeric level
                }));
                console.log(`✅ Loaded ${this._networks.length} surface networks from API`);
            } else {
                console.error('❌ Invalid networks response:', response);
                this._networks = [];
            }
        } catch (error) {
            console.error('❌ Failed to load networks from API:', error);
            this._networks = [];
        }

        return this._networks;
    },

    normalizePermissionAction: function (action: unknown = PermissionAction.READ): Action {
        const normalized = String(action || '').toLowerCase();
        if (
            normalized === PermissionAction.READ ||
            normalized === PermissionAction.WRITE ||
            normalized === PermissionAction.DELETE
        ) {
            return normalized;
        }
        return PermissionAction.READ;
    },

    normalizeProjectPermissionLabel: function (permission: unknown) {
        if (!permission) return null;
        const normalized = String(permission).trim().toUpperCase().replace(/\s+/g, '_');
        return normalized || null;
    },

    getProjectById: function (projectId: EntityId | null | undefined) {
        if (!projectId) return null;
        return this.projects.find(project => project.id === String(projectId)) || null;
    },

    getNetworkById: function (networkId: EntityId | null | undefined) {
        if (!networkId) return null;
        return this.networks.find(network => network.id === String(networkId)) || null;
    },

    getGPSTrackById: function (trackId: EntityId | null | undefined) {
        if (!trackId) return null;
        return this.gpsTracks.find(track => track.id === String(trackId)) || null;
    },

    getGISLayerById: function (layerId: EntityId | null | undefined) {
        if (!layerId) return null;
        return this.gisLayers.find(layer => layer.id === String(layerId)) || null;
    },

    getProjectPermissionRank: function (projectId: EntityId | null | undefined) {
        const project = this.getProjectById(projectId);
        if (!project) return ProjectPermissionRank.UNKNOWN;

        const normalized = this.normalizeProjectPermissionLabel(project.permissions);
        if (normalized === 'ADMIN') return ProjectPermissionRank.ADMIN;
        if (normalized === 'READ_AND_WRITE') return ProjectPermissionRank.READ_AND_WRITE;
        if (normalized === 'READ_ONLY') return ProjectPermissionRank.READ_ONLY;
        if (normalized === 'WEB_VIEWER') return ProjectPermissionRank.WEB_VIEWER;
        return ProjectPermissionRank.UNKNOWN;
    },

    getNetworkPermissionLevel: function (networkId: EntityId | null | undefined) {
        const network = this.getNetworkById(networkId);
        if (!network) return 0;

        if (typeof network.permission_level === 'number' && Number.isFinite(network.permission_level)) {
            return network.permission_level;
        }

        const normalized = this.normalizeProjectPermissionLabel(network.permissions);
        if (normalized === 'ADMIN') return 3;
        if (normalized === 'READ_AND_WRITE') return 2;
        if (normalized === 'READ_ONLY') return 1;
        return 0;
    },

    hasProjectAccess: function (projectId: EntityId | null | undefined, action: unknown = PermissionAction.READ) {
        try {
            const normalizedAction = this.normalizePermissionAction(action);
            const rank = this.getProjectPermissionRank(projectId);
            return rank >= ProjectActionMinRank[normalizedAction];
        } catch (e) {
            return false;
        }
    },

    hasNetworkAccess: function (networkId: EntityId | null | undefined, action: unknown = PermissionAction.READ) {
        try {
            const normalizedAction = this.normalizePermissionAction(action);
            const level = this.getNetworkPermissionLevel(networkId);
            return level >= NetworkActionMinLevel[normalizedAction];
        } catch (e) {
            return false;
        }
    },

    getProjectAccess: function (projectId: EntityId | null | undefined) {
        return {
            read: this.hasProjectAccess(projectId, PermissionAction.READ),
            write: this.hasProjectAccess(projectId, PermissionAction.WRITE),
            delete: this.hasProjectAccess(projectId, PermissionAction.DELETE),
        };
    },

    getNetworkAccess: function (networkId: EntityId | null | undefined) {
        return {
            read: this.hasNetworkAccess(networkId, PermissionAction.READ),
            write: this.hasNetworkAccess(networkId, PermissionAction.WRITE),
            delete: this.hasNetworkAccess(networkId, PermissionAction.DELETE),
        };
    },

    hasScopedAccess: function (scopeType: string, scopeId: EntityId | null | undefined, action: unknown = PermissionAction.READ) {
        if (scopeType === 'gis_geometry') return this.hasGISGeometryAccess(scopeId, action);
        if (scopeType === 'network') {
            return this.hasNetworkAccess(scopeId, action);
        }
        return this.hasProjectAccess(scopeId, action);
    },

    getScopedAccess: function (scopeType: string, scopeId: EntityId | null | undefined) {
        if (scopeType === 'gis_geometry') {
            return {
                read: this.hasGISGeometryAccess(scopeId, PermissionAction.READ),
                write: this.hasGISGeometryAccess(scopeId, PermissionAction.WRITE),
                delete: this.hasGISGeometryAccess(scopeId, PermissionAction.DELETE),
            };
        }
        if (scopeType === 'network') {
            return this.getNetworkAccess(scopeId);
        }
        return this.getProjectAccess(scopeId);
    },

    getStationScope: function (station: StationScopeRecord | null | undefined) {
        if (!station) {
            return { scopeType: 'project', scopeId: null };
        }
        const isSurfaceStation = Boolean(station.network) || station.station_type === 'surface';
        return {
            scopeType: isSurfaceStation ? 'network' : 'project',
            scopeId: isSurfaceStation ? station.network : station.project,
        };
    },

    getStationAccess: function (station: StationScopeRecord | null | undefined) {
        const { scopeType, scopeId } = this.getStationScope(station);
        const access = this.getScopedAccess(scopeType, scopeId);
        return {
            scopeType,
            scopeId,
            ...access,
        };
    },

    // Backward-compatible helpers now routed to central permission logic.
    hasProjectReadAccess: function (projectId: EntityId | null | undefined) {
        return this.hasProjectAccess(projectId, PermissionAction.READ);
    },

    hasProjectWriteAccess: function (projectId: EntityId | null | undefined) {
        return this.hasProjectAccess(projectId, PermissionAction.WRITE);
    },

    hasProjectAdminAccess: function (projectId: EntityId | null | undefined) {
        return this.hasProjectAccess(projectId, PermissionAction.DELETE);
    },

    hasNetworkReadAccess: function (networkId: EntityId | null | undefined) {
        return this.hasNetworkAccess(networkId, PermissionAction.READ);
    },

    hasNetworkWriteAccess: function (networkId: EntityId | null | undefined) {
        return this.hasNetworkAccess(networkId, PermissionAction.WRITE);
    },

    hasNetworkAdminAccess: function (networkId: EntityId | null | undefined) {
        return this.hasNetworkAccess(networkId, PermissionAction.DELETE);
    },

    /**
     * Filter projects to only include those with available GeoJSON data.
     * Call this after fetching GeoJSON metadata to remove projects without map data.
     * @param {Array} geojsonMetadata - Array of project metadata with geojson_file field
     */
    filterProjectsByGeoJSON: function (geojsonMetadata: Pick<ProjectResponse, 'id' | 'geojson_file'>[] | null) {
        if (!this._projects || !Array.isArray(geojsonMetadata)) {
            return;
        }

        const projectsWithGeoJSON = new Set();

        // Build a set of project IDs that have valid GeoJSON
        geojsonMetadata.forEach(meta => {
            if (meta.geojson_file) {
                projectsWithGeoJSON.add(String(meta.id));
            }
        });

        // Also check for projects that have geojson_url directly set
        this._projects.forEach(p => {
            if (p.geojson_url) {
                projectsWithGeoJSON.add(String(p.id));
            }
        });

        const originalCount = this._projects.length;

        // Filter to only keep projects with GeoJSON
        this._projects = this._projects.filter(p => projectsWithGeoJSON.has(String(p.id)));

        const filteredCount = originalCount - this._projects.length;
        if (filteredCount > 0) {
            console.log(`🗺️ Filtered out ${filteredCount} projects without GeoJSON data`);
        }
        console.log(`✅ ${this._projects.length} projects with GeoJSON available for map viewer`);
    },
    VISIBILITY_PREFS_STORAGE_KEY: DEFAULTS.STORAGE_KEYS.PROJECT_VISIBILITY,
    NETWORK_VISIBILITY_PREFS_STORAGE_KEY: DEFAULTS.STORAGE_KEYS.NETWORK_VISIBILITY,

    // Load GPS tracks from API (call this early in initialization)
    async loadGPSTracks({ force = false, throwOnError = false }: LoadOverlayOptions = {}) {
        if (this._gpsTracks && !force) {
            return this._gpsTracks;
        }

        try {
            console.log('🔄 Loading GPS tracks from API...');
            const response = await API.getGPSTracks();

            if (Array.isArray(response)) {
                this._gpsTracks = response.map(t => ({
                    id: String(t.id),
                    name: t.name,
                    color: t.color,
                    file: t.file, // URL to download the GeoJSON
                    creation_date: t.creation_date,
                    modified_date: t.modified_date,
                }));
                console.log(`✅ Loaded ${this._gpsTracks.length} GPS tracks from API`);
            } else {
                if (throwOnError) throw new Error('Invalid GPS tracks response');
                console.error('❌ Invalid GPS tracks response:', response);
                this._gpsTracks = [];
            }
        } catch (error) {
            console.error('❌ Failed to load GPS tracks from API:', error);
            if (throwOnError) throw error;
            this._gpsTracks = [];
        }

        return this._gpsTracks;
    },

    async loadGISLayers({ force = false, throwOnError = false }: LoadOverlayOptions = {}) {
        if (this._gisLayers && !force) {
            return this._gisLayers;
        }

        try {
            const response = await API.getGISLayers();
            if (throwOnError && !Array.isArray(response)) throw new Error('Invalid GIS Layers response');
            this._gisLayers = Array.isArray(response)
                ? response.map(layer => ({ ...layer, id: String(layer.id) }))
                : [];
        } catch (error) {
            console.error('Failed to load GIS Layers:', error);
            if (throwOnError) throw error;
            this._gisLayers = [];
        }

        return this._gisLayers;
    }
};
