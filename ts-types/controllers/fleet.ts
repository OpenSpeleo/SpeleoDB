import type { EntityId } from '../domain/identifiers.ts';
export type FleetDetailRoute = 'api:v2:cylinder-detail' | 'api:v2:sensor-detail';
export type FleetExportRoute = 'api:v2:cylinder-fleet-watchlist-export' | 'api:v2:sensor-fleet-watchlist-export';
export interface FleetContext {
    kind?: 'cylinder' | 'sensor';
    mode?: 'details' | 'watchlist';
    tableSelector?: string;
    hasRows?: boolean;
    hasWrite?: boolean;
    orderAscending?: boolean;
    showDaysFilter?: boolean;
    settingsEndpoint?: string;
    settingsMessage?: string;
    entityCrud?: boolean;
    listEndpoint?: string;
    detailRoute?: FleetDetailRoute;
    exportRoute?: FleetExportRoute;
    fleetId?: EntityId;
}
