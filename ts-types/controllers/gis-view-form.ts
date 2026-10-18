import type { GISView } from '@speleodb/api';
import type { GisViewFormOptions } from '../domain/forms/gis-view.ts';

export type GisViewSaved = Pick<GISView, 'id'>;
export interface GisViewFormContext extends Omit<GisViewFormOptions<GisViewSaved>, 'save' | 'loadProjects' | 'loadCommits'> {
    viewId?: string;
    redirectRoute?: 'private:gis_view_details';
}
