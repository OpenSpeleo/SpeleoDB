import type { Feature, FeatureCollection, LineString, Point, Polygon } from 'geojson';
import type { EditableGeometry, GeometryDraft, Position2D } from './geometry-editor.ts';
import type { EntityId } from './identifiers.ts';
import type { GISGeometryResponse } from './map-config.ts';
import type { MapGestureToggle } from './map-interactions.ts';
import type { RendererLayer } from './renderer.ts';
import type { LongitudeLatitude, ScreenPoint } from './measurement.ts';

export interface EditorInput {
    lngLat?: LongitudeLatitude;
    lngLats?: LongitudeLatitude[];
    point?: ScreenPoint;
    points?: ScreenPoint[];
    originalEvent?: { button?: number };
    preventDefault?(): void;
}
export interface EditorFeatureProperties {
    role: 'shape' | 'preview' | 'vertex' | 'midpoint' | 'bbox';
    color?: string;
    index?: number;
    selected?: boolean;
}
export type EditorFeature = Feature<Point | LineString | Polygon, EditorFeatureProperties>;
export type EditorCollection = FeatureCollection<EditorFeature['geometry'], EditorFeatureProperties>;
export interface EditorMap {
    getContainer(): HTMLElement;
    getCanvas(): HTMLElement;
    getStyle?(): unknown;
    getLayer(id: string): RendererLayer | undefined;
    addLayer(layer: RendererLayer): unknown;
    removeLayer(id: string): unknown;
    getSource(id: string): { setData(data: EditorCollection): unknown } | undefined;
    addSource(id: string, definition: { type: 'geojson'; data: EditorCollection; tolerance: number }): unknown;
    removeSource(id: string): unknown;
    queryRenderedFeatures(bounds: number[][], options: { layers: string[] }): Feature<Point, EditorFeatureProperties>[];
    dragPan?: MapGestureToggle;
    doubleClickZoom?: MapGestureToggle;
    on?(event: 'dblclick', handler: (event: EditorInput) => void): unknown;
    off?(event: 'dblclick', handler: (event: EditorInput) => void): unknown;
}
export interface EditorSession {
    record: GISGeometryResponse | null;
    name: string;
    color: string;
    draft: GeometryDraft;
    selected: number | null;
    drawing: boolean;
    preview: Position2D | null;
    drag: { snapshot: Position2D[]; start: ScreenPoint | undefined; moved: boolean; panEnabled: boolean } | null;
    saving: boolean;
    error: string;
    gpsDirty: boolean;
    discardRequested: boolean;
    conflict: boolean;
    doubleClickEnabled: boolean;
    originalSignature?: string;
    returnFocus?: HTMLElement | null;
    suppressClick?: boolean;
    reloadRequested?: boolean;
    pendingAction?: (() => unknown) | null;
}
export interface EditorNodes {
    root: HTMLElement;
    name: HTMLInputElement;
    types: HTMLDivElement;
    colors: HTMLDivElement;
    currentColor: HTMLSpanElement;
    hint: HTMLParagraphElement;
    toolbar: HTMLDivElement;
    vertices: HTMLDivElement;
    gps: HTMLFormElement;
    gpsDisclosure: HTMLDetailsElement;
    gpsTitle: HTMLHeadingElement;
    latitude: HTMLInputElement;
    longitude: HTMLInputElement;
    apply: HTMLButtonElement;
    area: HTMLDivElement;
    areaValue: HTMLElement;
    progressFill: HTMLSpanElement;
    status: HTMLParagraphElement;
    discard: HTMLDivElement;
    conflict: HTMLDivElement;
    copyFallback: HTMLTextAreaElement;
    save: HTMLButtonElement;
}
export interface EditorActivity { opening: boolean | undefined; active: boolean }
export interface EditorOptions {
    map: EditorMap;
    onSaved?: (record: GISGeometryResponse) => unknown;
    onLoaded?: (record: GISGeometryResponse) => unknown;
    onPreview?: (id: EntityId | null, active: boolean) => unknown;
    onActivityChange?: (state: EditorActivity) => unknown;
    palette?: string[];
}
export interface GeometryEditorFacade {
    map?: EditorMap;
    session?: EditorSession | null;
    nodes?: EditorNodes | null;
    palette?: string[];
    onSaved?: NonNullable<EditorOptions['onSaved']>;
    onLoaded?: NonNullable<EditorOptions['onLoaded']>;
    onPreview?: NonNullable<EditorOptions['onPreview']>;
    onActivityChange?: NonNullable<EditorOptions['onActivityChange']>;
    _opening?: boolean | undefined;
    _keyHandler?: (event: KeyboardEvent) => void;
    _leaveHandler?: (event: BeforeUnloadEvent) => void;
    _outsideUp?: (event: Event) => void;
    _cancelDrag?: () => void;
    _doubleClick?: (event: EditorInput) => void;
    _queueViewportUpdate?: (() => void) | null;
    _viewportFrame?: number | null;
    _viewportObserver?: ResizeObserver | null;
    _observedVisualViewport?: VisualViewport | null;
    init(options: EditorOptions): GeometryEditorFacade;
    isActive(): boolean;
    isOpening(): boolean | undefined;
    notifyActivityChange(): void;
    hasUnsavedChanges(): boolean;
    signature(): string;
    create(): Promise<boolean>;
    edit(record: Pick<GISGeometryResponse, 'id'> | null): Promise<boolean>;
    begin(record: GISGeometryResponse | null): void;
    observeViewport(): void;
    positionWithinViewport(): void;
    stopObservingViewport(): void;
    buildUI(): void;
    button(action: string, label: string, text: string): HTMLButtonElement;
    coordinateInput(title: string, placeholder: string): { label: HTMLLabelElement; input: HTMLInputElement };
    performAction(action: string, button?: HTMLButtonElement): void;
    select(index: number | null): void;
    applyGPS(): boolean;
    flushGPS(): boolean;
    prospectiveGeometry(): EditableGeometry;
    copyDraft(): Promise<boolean>;
    reloadSaved(): Promise<boolean>;
    append(coordinates: Position2D, index?: number | null): boolean;
    hit(event: EditorInput): Feature<Point, EditorFeatureProperties> | null;
    handleClick(event: EditorInput): boolean;
    handleMouseDown(event: EditorInput): boolean;
    handleMouseMove(event: EditorInput): boolean;
    handleMouseUp(): boolean;
    handleCancel(): boolean;
    finishDrag(): void;
    cancelDrag(): void;
    handleContextMenu(event: EditorInput): boolean;
    handleKeyDown(event: KeyboardEvent): void;
    save(): Promise<boolean>;
    requestClose(next?: (() => unknown) | null): boolean;
    close(force?: boolean): void;
    refreshUI(refreshVertices?: boolean): void;
    render(refreshVertices?: boolean): void;
    restoreLayers(): void;
    renderMap(): void;
    removeLayers(): void;
    destroy(): void;
}
