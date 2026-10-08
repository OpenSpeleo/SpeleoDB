import type { StationResourceRecord } from './station-records.ts';
/** Preview fallbacks accept absent metadata; mutations retain full API records. */
export type StationResourcePreview = Pick<StationResourceRecord, 'resource_type'> & Partial<Omit<StationResourceRecord, 'resource_type'>> & { is_demo?: boolean };
export interface StationNotePresentation {
    title?: string | undefined;
    content: string;
    description?: string | undefined;
    author?: string | undefined;
    date?: string | undefined;
}
