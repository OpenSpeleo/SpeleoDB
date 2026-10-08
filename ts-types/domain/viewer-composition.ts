import type { MapCoreMap } from './map-core.ts';
import type { LegendMap } from './map-depth-legend.ts';
import type { ProjectResponse } from './map-config.ts';
import type { EditorMap } from './geometry-editor-runtime.ts';
import type { InteractionMap } from './map-interactions.ts';
import type { MeasurementToolMap } from './measurement-tool.ts';
import type { ViewerNavigationMap } from './map-runtime.ts';

export type PublicViewerMap = MapCoreMap & LegendMap & { setMaxZoom(zoom: number): unknown };
export interface PublicViewerData { projects?: ProjectResponse[]; view_name?: string }
export interface PublicViewerLoadOptions { fetchProjects?: boolean; fitCamera?: boolean; hideOverlay?: boolean }

export type PrivateViewerMap = MapCoreMap & LegendMap & EditorMap & InteractionMap & MeasurementToolMap & ViewerNavigationMap & { addControl(control: { onAdd(map: MeasurementToolMap): HTMLElement; onRemove(): void }, position: 'top-right'): unknown };
export interface PrivateViewerLoadOptions extends PublicViewerLoadOptions {
    initializePanels?: boolean;
    initializeTags?: boolean;
    showProgress?: boolean;
}
