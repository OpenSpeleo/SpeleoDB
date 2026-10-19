import * as sdk from '@speleodb/api';
import { apiData, webApiOptions } from './client.ts';
import { field, choice } from './entity-forms.ts';
import type { PermissionOperations } from '../../ts-types/domain/forms/permissions.ts';

export type PermissionResource = 'project' | 'surface-network' | 'cylinder-fleet' | 'sensor-fleet' | 'landmark-collection' | 'experiment' | 'gis-geometry' | 'gis-layer' | 'gps-track' | 'team';

export function userPermissions(resource: PermissionResource, id: string): PermissionOperations {
    switch (resource) {
        case 'project': return {
            create: payload => apiData(sdk.v2ProjectsPermissionUserDetailCreateWithJson(id, { user: field(payload, 'user'), level: field(payload, 'level') }, undefined, webApiOptions())),
            update: payload => apiData(sdk.v2ProjectsPermissionUserDetailUpdateWithJson(id, { user: field(payload, 'user'), level: field(payload, 'level') }, undefined, webApiOptions())),
            remove: payload => apiData(sdk.v2ProjectsPermissionUserDetailDestroyWithJson(id, { user: field(payload, 'user') }, undefined, webApiOptions())),
        };
        case 'surface-network': return {
            create: payload => apiData(sdk.v2SurfaceNetworksPermissionsCreateWithJson(id, { user: field(payload, 'user'), level: field(payload, 'level') }, undefined, webApiOptions())),
            update: payload => apiData(sdk.v2SurfaceNetworksPermissionsUpdateWithJson(id, { user: field(payload, 'user'), level: field(payload, 'level') }, undefined, webApiOptions())),
            remove: payload => apiData(sdk.v2SurfaceNetworksPermissionsDestroyWithJson(id, { user: field(payload, 'user') }, undefined, webApiOptions())),
        };
        case 'cylinder-fleet': return {
            create: payload => apiData(sdk.v2CylinderFleetsPermissionsCreateWithJson(id, { user: field(payload, 'user'), level: field(payload, 'level') }, undefined, webApiOptions())),
            update: payload => apiData(sdk.v2CylinderFleetsPermissionsUpdateWithJson(id, { user: field(payload, 'user'), level: field(payload, 'level') }, undefined, webApiOptions())),
            remove: payload => apiData(sdk.v2CylinderFleetsPermissionsDestroyWithJson(id, { user: field(payload, 'user') }, undefined, webApiOptions())),
        };
        case 'sensor-fleet': return {
            create: payload => apiData(sdk.v2SensorFleetsPermissionsCreateWithJson(id, { user: field(payload, 'user'), level: field(payload, 'level') }, undefined, webApiOptions())),
            update: payload => apiData(sdk.v2SensorFleetsPermissionsUpdateWithJson(id, { user: field(payload, 'user'), level: field(payload, 'level') }, undefined, webApiOptions())),
            remove: payload => apiData(sdk.v2SensorFleetsPermissionsDestroyWithJson(id, { user: field(payload, 'user') }, undefined, webApiOptions())),
        };
        case 'landmark-collection': return {
            create: payload => apiData(sdk.v2LandmarkCollectionsPermissionsCreateWithJson(id, { user: field(payload, 'user'), level: field(payload, 'level') }, undefined, webApiOptions())),
            update: payload => apiData(sdk.v2LandmarkCollectionsPermissionsUpdateWithJson(id, { user: field(payload, 'user'), level: field(payload, 'level') }, undefined, webApiOptions())),
            remove: payload => apiData(sdk.v2LandmarkCollectionsPermissionsDestroyWithJson(id, { user: field(payload, 'user') }, undefined, webApiOptions())),
        };
        case 'experiment': return {
            create: payload => apiData(sdk.v2ExperimentsPermissionDetailCreateWithJson(id, { user: field(payload, 'user'), level: field(payload, 'level') }, undefined, webApiOptions())),
            update: payload => apiData(sdk.v2ExperimentsPermissionDetailUpdateWithJson(id, { user: field(payload, 'user'), level: field(payload, 'level') }, undefined, webApiOptions())),
            remove: payload => apiData(sdk.v2ExperimentsPermissionDetailDestroyWithJson(id, { user: field(payload, 'user') }, undefined, webApiOptions())),
        };
        case 'gis-geometry': return {
            create: payload => apiData(sdk.v2GisGeometriesPermissionsCreateWithJson(id, { user: field(payload, 'user'), level: field(payload, 'level') }, undefined, webApiOptions())),
            update: payload => apiData(sdk.v2GisGeometriesPermissionsUpdateWithJson(id, { user: field(payload, 'user'), level: field(payload, 'level') }, undefined, webApiOptions())),
            remove: payload => apiData(sdk.v2GisGeometriesPermissionsDestroyWithJson(id, { user: field(payload, 'user') }, undefined, webApiOptions())),
        };
        case 'gis-layer': return {
            create: payload => apiData(sdk.v2GisLayersPermissionsCreateWithJson(id, { user: field(payload, 'user'), level: field(payload, 'level') }, undefined, webApiOptions())),
            update: payload => apiData(sdk.v2GisLayersPermissionsUpdateWithJson(id, { user: field(payload, 'user'), level: field(payload, 'level') }, undefined, webApiOptions())),
            remove: payload => apiData(sdk.v2GisLayersPermissionsDestroyWithJson(id, { user: field(payload, 'user') }, undefined, webApiOptions())),
        };
        case 'gps-track': return {
            create: payload => apiData(sdk.v2GpsTracksPermissionsCreateWithJson(id, { user: field(payload, 'user'), level: field(payload, 'level') }, undefined, webApiOptions())),
            update: payload => apiData(sdk.v2GpsTracksPermissionsUpdateWithJson(id, { user: field(payload, 'user'), level: field(payload, 'level') }, undefined, webApiOptions())),
            remove: payload => apiData(sdk.v2GpsTracksPermissionsDestroyWithJson(id, { user: field(payload, 'user') }, undefined, webApiOptions())),
        };
        case 'team': return {
            create: payload => apiData(sdk.v2TeamsMembershipsDetailCreateWithJson(id, { user: field(payload, 'user'), role: choice(sdk.UserRequestWithTeamRoleRequestRole, payload.role) }, undefined, webApiOptions())),
            update: payload => apiData(sdk.v2TeamsMembershipsDetailUpdateWithJson(id, { user: field(payload, 'user'), role: choice(sdk.UserRequestWithTeamRoleRequestRole, payload.role) }, undefined, webApiOptions())),
            remove: payload => apiData(sdk.v2TeamsMembershipsDetailDestroyWithJson(id, { user: field(payload, 'user') }, undefined, webApiOptions())),
        };
    }
}

export function teamPermissions(projectId: string): PermissionOperations {
    return {
        create: payload => apiData(sdk.v2ProjectsPermissionTeamDetailCreateWithJson(projectId, { team: field(payload, 'team'), level: choice(sdk.TeamRequestWithProjectLevelRequestLevel, payload.level) }, undefined, webApiOptions())),
        update: payload => apiData(sdk.v2ProjectsPermissionTeamDetailUpdateWithJson(projectId, { team: field(payload, 'team'), level: choice(sdk.TeamRequestWithProjectLevelRequestLevel, payload.level) }, undefined, webApiOptions())),
        remove: payload => apiData(sdk.v2ProjectsPermissionTeamDetailDestroyWithJson(projectId, { team: field(payload, 'team') }, undefined, webApiOptions())),
    };
}
