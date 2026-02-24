import { API } from './api.js';

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
    _projects: null,

    // Private storage for networks loaded from API
    _networks: null,

    // Private storage for GPS tracks loaded from API
    _gpsTracks: null,

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

    // Load projects from API (call this early in initialization)
    async loadProjects() {
        if (this._projects) {
            return this._projects;
        }

        try {
            console.log('🔄 Loading projects from API...');
            const response = await API.getAllProjects();

            if (response && response.success && Array.isArray(response.data)) {
                // Map API response to expected format (permission -> permissions)
                this._projects = response.data.map(p => ({
                    id: p.id,
                    name: p.name,
                    permissions: p.permission,  // API returns 'permission', code expects 'permissions'
                    description: p.description,
                    country: p.country,
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

            if (response && response.success && Array.isArray(response.data)) {
                // Map API response to expected format
                this._networks = response.data.map(n => ({
                    id: n.id,
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

    normalizePermissionAction: function (action = PermissionAction.READ) {
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

    normalizeProjectPermissionLabel: function (permission) {
        if (!permission) return null;
        const normalized = String(permission).trim().toUpperCase().replace(/\s+/g, '_');
        return normalized || null;
    },

    getProjectById: function (projectId) {
        if (!projectId) return null;
        return this.projects.find(project => project.id === String(projectId)) || null;
    },

    getNetworkById: function (networkId) {
        if (!networkId) return null;
        return this.networks.find(network => network.id === String(networkId)) || null;
    },

    getProjectPermissionRank: function (projectId) {
        const project = this.getProjectById(projectId);
        if (!project) return ProjectPermissionRank.UNKNOWN;

        const normalized = this.normalizeProjectPermissionLabel(project.permissions);
        if (normalized === 'ADMIN') return ProjectPermissionRank.ADMIN;
        if (normalized === 'READ_AND_WRITE') return ProjectPermissionRank.READ_AND_WRITE;
        if (normalized === 'READ_ONLY') return ProjectPermissionRank.READ_ONLY;
        if (normalized === 'WEB_VIEWER') return ProjectPermissionRank.WEB_VIEWER;
        return ProjectPermissionRank.UNKNOWN;
    },

    getNetworkPermissionLevel: function (networkId) {
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

    hasProjectAccess: function (projectId, action = PermissionAction.READ) {
        try {
            const normalizedAction = this.normalizePermissionAction(action);
            const rank = this.getProjectPermissionRank(projectId);
            return rank >= ProjectActionMinRank[normalizedAction];
        } catch (e) {
            return false;
        }
    },

    hasNetworkAccess: function (networkId, action = PermissionAction.READ) {
        try {
            const normalizedAction = this.normalizePermissionAction(action);
            const level = this.getNetworkPermissionLevel(networkId);
            return level >= NetworkActionMinLevel[normalizedAction];
        } catch (e) {
            return false;
        }
    },

    getProjectAccess: function (projectId) {
        return {
            read: this.hasProjectAccess(projectId, PermissionAction.READ),
            write: this.hasProjectAccess(projectId, PermissionAction.WRITE),
            delete: this.hasProjectAccess(projectId, PermissionAction.DELETE),
        };
    },

    getNetworkAccess: function (networkId) {
        return {
            read: this.hasNetworkAccess(networkId, PermissionAction.READ),
            write: this.hasNetworkAccess(networkId, PermissionAction.WRITE),
            delete: this.hasNetworkAccess(networkId, PermissionAction.DELETE),
        };
    },

    hasScopedAccess: function (scopeType, scopeId, action = PermissionAction.READ) {
        if (scopeType === 'network') {
            return this.hasNetworkAccess(scopeId, action);
        }
        return this.hasProjectAccess(scopeId, action);
    },

    getScopedAccess: function (scopeType, scopeId) {
        if (scopeType === 'network') {
            return this.getNetworkAccess(scopeId);
        }
        return this.getProjectAccess(scopeId);
    },

    getStationScope: function (station) {
        if (!station) {
            return { scopeType: 'project', scopeId: null };
        }
        const isSurfaceStation = Boolean(station.network) || station.station_type === 'surface';
        return {
            scopeType: isSurfaceStation ? 'network' : 'project',
            scopeId: isSurfaceStation ? station.network : station.project,
        };
    },

    getStationAccess: function (station) {
        const { scopeType, scopeId } = this.getStationScope(station);
        const access = this.getScopedAccess(scopeType, scopeId);
        return {
            scopeType,
            scopeId,
            ...access,
        };
    },

    // Backward-compatible helpers now routed to central permission logic.
    hasProjectReadAccess: function (projectId) {
        return this.hasProjectAccess(projectId, PermissionAction.READ);
    },

    hasProjectWriteAccess: function (projectId) {
        return this.hasProjectAccess(projectId, PermissionAction.WRITE);
    },

    hasProjectAdminAccess: function (projectId) {
        return this.hasProjectAccess(projectId, PermissionAction.DELETE);
    },

    hasNetworkReadAccess: function (networkId) {
        return this.hasNetworkAccess(networkId, PermissionAction.READ);
    },

    hasNetworkWriteAccess: function (networkId) {
        return this.hasNetworkAccess(networkId, PermissionAction.WRITE);
    },

    hasNetworkAdminAccess: function (networkId) {
        return this.hasNetworkAccess(networkId, PermissionAction.DELETE);
    },

    /**
     * Filter projects to only include those with available GeoJSON data.
     * Call this after fetching GeoJSON metadata to remove projects without map data.
     * @param {Array} geojsonMetadata - Array of project metadata with geojson_file field
     */
    filterProjectsByGeoJSON: function (geojsonMetadata) {
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
    VISIBILITY_PREFS_STORAGE_KEY: 'speleo_project_visibility',
    NETWORK_VISIBILITY_PREFS_STORAGE_KEY: 'speleo_network_visibility',

    // Load GPS tracks from API (call this early in initialization)
    async loadGPSTracks() {
        if (this._gpsTracks) {
            return this._gpsTracks;
        }

        try {
            console.log('🔄 Loading GPS tracks from API...');
            const response = await API.getGPSTracks();

            if (response && response.success && Array.isArray(response.data)) {
                // Map API response to expected format
                this._gpsTracks = response.data.map(t => ({
                    id: t.id,
                    name: t.name,
                    file: t.file, // URL to download the GeoJSON
                    sha256_hash: t.sha256_hash,
                    creation_date: t.creation_date,
                    modified_date: t.modified_date,
                }));
                console.log(`✅ Loaded ${this._gpsTracks.length} GPS tracks from API`);
            } else {
                console.error('❌ Invalid GPS tracks response:', response);
                this._gpsTracks = [];
            }
        } catch (error) {
            console.error('❌ Failed to load GPS tracks from API:', error);
            this._gpsTracks = [];
        }

        return this._gpsTracks;
    }
};
