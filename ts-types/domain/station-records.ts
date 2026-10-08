import type { EntityId } from './identifiers.ts';

/** Fields shared by persisted GIS records serialized by Django. */
export interface RecordDates {
    created_by?: string;
    creation_date?: string;
    modified_date?: string;
}
export interface StationWrite {
    name?: string;
    description?: string;
    latitude?: string | number;
    longitude?: string | number;
    type?: string;
    tag?: EntityId | null;
}
export interface StationRecord extends Omit<StationWrite, 'tag'>, RecordDates {
    id: EntityId;
    project?: EntityId | null | undefined;
    network?: EntityId | null | undefined;
    station_type?: string;
    is_demo?: boolean;
    snapped_to_line?: string;
    tag?: Pick<StationTagRecord, 'id' | 'name' | 'color'> | null;
    tag_name?: string | null;
    tag_color?: string | null;
}
export interface StationTagRecord extends RecordDates {
    id: EntityId;
    name: string;
    color: string;
    station_count?: number;
}
export interface StationLogRecord extends RecordDates {
    id: EntityId;
    station: EntityId;
    title: string;
    notes: string;
    attachment: string | null;
}
export interface StationResourceRecord extends RecordDates {
    id: EntityId;
    station: EntityId;
    resource_type: string;
    title: string;
    description: string;
    file: string | null;
    miniature: string | null;
    text_content: string;
}
export interface LeadWrite {
    description?: string;
    latitude?: string | number;
    longitude?: string | number;
}
export interface LeadRecord extends Omit<LeadWrite, 'latitude' | 'longitude'>, RecordDates {
    id: EntityId;
    project: EntityId;
    latitude: string;
    longitude: string;
}
