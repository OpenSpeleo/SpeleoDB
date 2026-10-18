import * as sdk from '@speleodb/api';
import { apiData, webApiOptions } from './client.ts';
import type { FormPayload } from '../../ts-types/domain/forms/crud.ts';

export type FormResource = 'project' | 'team' | 'surface-network' | 'sensor-fleet' | 'cylinder-fleet' | 'landmark-collection' | 'gis-layer' | 'gps-track' | 'user' | 'preferences' | 'password';
export type DeletableResource = Exclude<FormResource, 'user' | 'preferences' | 'password'> | 'experiment' | 'gis-view' | 'gis-geometry';

export function field(payload: FormPayload, name: string): string {
    const value = payload[name];
    if (typeof value !== 'string') throw new Error(`Missing form field: ${name}`);
    return value;
}

export function choice<T extends string>(values: Record<string, T>, value: unknown): T {
    const selected = Object.values(values).find(candidate => candidate === value);
    if (selected === undefined) throw new Error('Invalid selection.');
    return selected;
}

/** Forms select concrete generated operations; no server URL or HTTP verb comes from page context. */
export async function submitEntity(resource: FormResource, id: string | undefined, payload: FormPayload): Promise<unknown> {
    const options = webApiOptions();
    switch (resource) {
        case 'password': return apiData(sdk.v2UserPasswordUpdateWithJson({
            oldpassword: field(payload, 'oldpassword'), password1: field(payload, 'password1'), password2: field(payload, 'password2'),
        }, options));
        case 'preferences': return apiData(sdk.v2UserPartialUpdateWithJson({
            email_on_projects_updates: payload.email_on_projects_updates === true,
            email_on_speleodb_updates: payload.email_on_speleodb_updates === true,
        }, options));
        case 'user': return apiData(sdk.v2UserPartialUpdateWithJson({
            name: field(payload, 'name'), email: field(payload, 'email'),
            country: choice(sdk.UserRequestCountry, payload.country),
        }, options));
        case 'project': {
            const body: sdk.ProjectRequest = {
                name: field(payload, 'name'), description: field(payload, 'description'),
                country: choice(sdk.ProjectRequestCountry, payload.country), type: field(payload, 'type'),
                color: field(payload, 'color'), latitude: field(payload, 'latitude') || null, longitude: field(payload, 'longitude') || null,
            };
            return id ? apiData(sdk.v2ProjectsUpdateWithJson(id, body, options)) : apiData(sdk.v2ProjectsCreateWithJson(body, options));
        }
        case 'team': {
            const body: sdk.SurveyTeamRequest = { name: field(payload, 'name'), description: field(payload, 'description'), country: choice(sdk.SurveyTeamRequestCountry, payload.country) };
            return id ? apiData(sdk.v2TeamsUpdateWithJson(id, body, options)) : apiData(sdk.v2TeamsCreateWithJson(body, options));
        }
        case 'surface-network': {
            const body = { name: field(payload, 'name'), description: field(payload, 'description') };
            return id ? apiData(sdk.v2SurfaceNetworksUpdateWithJson(id, body, options)) : apiData(sdk.v2SurfaceNetworksCreateWithJson(body, options));
        }
        case 'sensor-fleet': {
            const body = { name: field(payload, 'name'), description: field(payload, 'description'), sensors: Array.isArray(payload.sensors) ? payload.sensors.map((value: unknown) => {
                if (!value || typeof value !== 'object' || !('name' in value) || typeof value.name !== 'string' || !('notes' in value) || typeof value.notes !== 'string') throw new Error('Invalid sensor.');
                return { name: value.name, notes: value.notes };
            }) : [] };
            return id ? apiData(sdk.v2SensorFleetsUpdateWithJson(id, body, options)) : apiData(sdk.v2SensorFleetsCreateWithJson(body, options));
        }
        case 'cylinder-fleet': {
            const body = { name: field(payload, 'name'), description: field(payload, 'description') };
            return id ? apiData(sdk.v2CylinderFleetsUpdateWithJson(id, body, options)) : apiData(sdk.v2CylinderFleetsCreateWithJson(body, options));
        }
        case 'landmark-collection': {
            const body = { name: field(payload, 'name'), description: field(payload, 'description'), color: field(payload, 'color') };
            return id ? apiData(sdk.v2LandmarkCollectionsUpdateWithJson(id, body, options)) : apiData(sdk.v2LandmarkCollectionsCreateWithJson(body, options));
        }
        case 'gis-layer': return apiData(sdk.v2GisLayersPartialUpdateWithJson(requiredId(id), {
            name: field(payload, 'name'), description: field(payload, 'description'), color: field(payload, 'color'),
        }, options));
        case 'gps-track': return apiData(sdk.v2GpsTracksPartialUpdateWithJson(requiredId(id), {
            name: field(payload, 'name'), color: field(payload, 'color'),
        }, options));
    }
}

function requiredId(id: string | undefined): string {
    if (!id) throw new Error('Missing entity identifier.');
    return id;
}

export function deleteEntity(resource: DeletableResource, id: string): Promise<unknown> {
    const options = webApiOptions();
    switch (resource) {
        case 'project': return apiData(sdk.v2ProjectsDestroy(id, options));
        case 'team': return apiData(sdk.v2TeamsDestroy(id, options));
        case 'surface-network': return apiData(sdk.v2SurfaceNetworksDestroy(id, options));
        case 'sensor-fleet': return apiData(sdk.v2SensorFleetsDestroy(id, options));
        case 'cylinder-fleet': return apiData(sdk.v2CylinderFleetsDestroy(id, options));
        case 'landmark-collection': return apiData(sdk.v2LandmarkCollectionsDestroy(id, options));
        case 'gis-layer': return apiData(sdk.v2GisLayersDestroy(id, options));
        case 'gps-track': return apiData(sdk.v2GpsTracksDestroy(id, options));
        case 'experiment': return apiData(sdk.v2ExperimentsDestroy(id, options));
        case 'gis-view': return apiData(sdk.v2UserGisViewsDestroy(id, options));
        case 'gis-geometry': return apiData(sdk.v2GisGeometriesDestroy(id, options));
    }
}
