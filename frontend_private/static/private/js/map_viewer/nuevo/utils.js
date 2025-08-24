const Utils = {
    // ============================== PERMISSION ========================= //

    hasProjectWriteAccess(projectId) {
        try {
            const arr = window.AppState.projects || [];
            const proj = arr.find(p => String(p.id) === String(projectId));
            if (!proj) return false;
            return proj.permissions === 'READ_AND_WRITE' || proj.permissions === 'ADMIN';
        } catch (_) {
            return false;
        }
    },

    hasProjectAdminAccess(projectId) {
        try {
            const arr = window.AppState.projects || [];
            const proj = arr.find(p => String(p.id) === String(projectId));
            if (!proj) return false;
            return proj.permissions === 'ADMIN';
        } catch (_) {
            return false;
        }
    }
};