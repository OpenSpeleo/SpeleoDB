import type { EntityId } from '../domain/identifiers.ts';
export interface FleetContext {
    kind?: 'cylinder' | 'sensor';
    mode?: 'details' | 'watchlist';
    tableSelector?: string;
    hasRows?: boolean;
    hasWrite?: boolean;
    orderAscending?: boolean;
    showDaysFilter?: boolean;
    settings?: boolean;
    settingsMessage?: string;
    entityCrud?: boolean;
    fleetId?: EntityId;
}
