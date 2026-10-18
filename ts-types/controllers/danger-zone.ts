import type { DangerZoneOptions } from '../domain/forms/crud.ts';
import type { DeletableResource } from '../../frontend_common/api/entity-forms.ts';

export interface DangerZoneContext extends Omit<DangerZoneOptions, 'remove'> {
    resource: DeletableResource;
    entityId: string;
}
