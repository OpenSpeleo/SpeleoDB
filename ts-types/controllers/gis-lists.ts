import type { GISLayerResponse } from '../domain/map-config.ts';

/** Shared listing fields delivered by GPS tracks and both GIS metadata endpoints. */
export type GISListRecord = GISLayerResponse;
export interface GISListContext {
    listEndpoint: string;
    openIconUrl?: string;
}
export interface GISUploadListContext extends GISListContext { csrfToken: string }
export type GISDetailsRoute = 'private:gis_layer_details' | 'private:gis_geometry_details';
export interface GISListPresentation {
    entityLabel: string;
    pluralLabel: string;
    detailsRoute: GISDetailsRoute;
    showSource: boolean;
    emptyHint: string;
}
export interface GISUploadErrorDetails {
    line?: number;
    column?: number;
    source_line?: string;
}
export interface GISUploadErrorBody {
    detail?: string;
    error?: string;
    error_message?: string;
    errors?: Record<string, unknown>;
    code?: string;
    details?: GISUploadErrorDetails;
}
