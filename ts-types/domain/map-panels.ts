import type { EntityId } from './identifiers.ts';
import type { GISGeometryMetadata } from './map-config.ts';

export interface GPSTracksPanelFacade {
    _rows: Map<string, HTMLDivElement>;
    _requests: Map<string, object>;
    _resizeObserver: ResizeObserver | null;
    _mutationObserver: MutationObserver | null;
    _loadingListener?: ((event: Event) => void) | null;
    init(): void;
    render(): void;
    positionPanel(): void;
    setupProjectPanelListener(): void;
    destroy(): void;
    refreshList(): void;
    activateAndFlyToTrack(trackId: EntityId): Promise<void>;
    flyToTrack(trackId: EntityId): void;
    toggleTrack(trackId: EntityId, isVisible: boolean): Promise<boolean>;
    updateRow(trackId: EntityId): void;
    bindEvents(): void;
    setupLoadingListener(): void;
    getTrackColor(trackId: EntityId): string;
}

/** The geometry panel needs only the editor's existing edit transition. */
export interface GeometryPanelEditor {
    edit(record: GISGeometryMetadata): Promise<boolean> | boolean;
}
