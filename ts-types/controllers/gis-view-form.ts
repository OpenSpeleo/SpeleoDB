import type { GisViewFormOptions } from '../domain/forms/gis-view.ts';
import type { EntityId } from '../domain/identifiers.ts';

export interface GisViewSaved { id: EntityId }
export interface GisViewFormContext extends GisViewFormOptions<GisViewSaved> {
    redirectRoute?: 'private:gis_view_details';
}
