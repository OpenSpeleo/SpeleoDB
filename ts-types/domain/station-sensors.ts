import type { EntityId } from './identifiers.ts';
export interface PendingSensorStatusChange {
    installId: EntityId;
    newStatus: string;
    stationId: EntityId;
    projectId: EntityId | null;
}
