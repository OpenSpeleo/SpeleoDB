export const Config = {
    get hasWriteAccess() {
        return window.SPELEO_CONTEXT?.hasWriteAccess || false;
    },
    
    get projects() {
        return window.SPELEO_CONTEXT?.projects || [];
    },

    get projectIds() {
        return this.projects.map(p => p.id);
    },

    // Helper: does the user have write access on a specific project?
    hasProjectWriteAccess: function(projectId) {
        try {
            const proj = this.projects.find(p => p.id === String(projectId));
            if (!proj) return false;
            // Treat READ_AND_WRITE and ADMIN as write access
            return proj.permissions === 'READ_AND_WRITE' || proj.permissions === 'ADMIN';
        } catch (e) {
            return false;
        }
    },

    // Helper: does the user have admin access on a specific project?
    hasProjectAdminAccess: function(projectId) {
        try {
            const proj = this.projects.find(p => p.id === String(projectId));
            if (!proj) return false;
            return proj.permissions === 'ADMIN';
        } catch (e) {
            return false;
        }
    },

    VISIBILITY_PREFS_STORAGE_KEY: 'speleo_project_visibility'
};


