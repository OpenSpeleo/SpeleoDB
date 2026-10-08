import type { EntityId } from '../domain/identifiers.ts';
import type { EntityCrudOptions } from '../domain/forms/crud.ts';

export interface CreatedEntity { id: EntityId }
export type EntityRedirectRoute =
    | 'private:sensor_fleet_details'
    | 'private:cylinder_fleet_details'
    | 'private:landmark_collection_details'
    | 'private:surface_network_details'
    | 'private:project_details';

export interface EntityCrudContext extends Pick<EntityCrudOptions<CreatedEntity>,
    'formId' | 'endpoint' | 'method' | 'successMessage' | 'successRedirect' | 'reloadOnSuccess'> {
    colorPicker?: boolean;
    sensorRows?: boolean;
    serializeCheckboxes?: boolean;
    requiredField?: 'name';
    requiredMessage?: string;
    redirectRoute?: EntityRedirectRoute;
}
