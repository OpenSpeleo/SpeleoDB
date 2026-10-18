import type {
    SubSurfaceStationWithResources, PatchedStationUpdateRequest,
    StationFeatureProperties, StationTag, StationLogEntry, StationResource,
    PatchedExplorationLeadRequest, ExplorationLead,
} from '@speleodb/api';
import type { EntityId } from './identifiers.ts';

/** Optional display timestamps also support unsaved local map records. */
export interface RecordDates {
    created_by?: string;
    creation_date?: string;
    modified_date?: string;
}
export type StationWrite = PatchedStationUpdateRequest;
/** Map state merges a detail DTO with its local scope and snapping state. */
export interface StationRecord extends Partial<Omit<SubSurfaceStationWithResources, 'id' | 'type' | 'project'>> {
    project?: EntityId | null | undefined;
    network?: EntityId | null | undefined;
    id: EntityId;
    type?: StationFeatureProperties['type'];
    station_type?: StationFeatureProperties['station_type'];
    is_demo?: boolean;
    snapped_to_line?: string;
    tag_name?: string | null;
    tag_color?: string | null;
}
export type StationTagRecord = StationTag;
export type StationLogRecord = StationLogEntry;
export type StationResourceRecord = StationResource;
export type LeadWrite = PatchedExplorationLeadRequest;
export type LeadRecord = ExplorationLead;
