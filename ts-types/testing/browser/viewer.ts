/** Only the real Mapbox methods observed by the browser instrumentation. */
export interface EvidenceMap {
    setLayoutProperty: (...args: unknown[]) => unknown;
    setPaintProperty: (...args: unknown[]) => unknown;
    setFilter: (...args: unknown[]) => unknown;
    moveLayer: (...args: unknown[]) => unknown;
    addSource: (id: string, source: unknown) => unknown;
    getSource(id: string): { setData?: (...args: unknown[]) => unknown } | undefined;
    getLayoutProperty(id: string, property: string): unknown;
    getPaintProperty(id: string, property: string): unknown;
    getFilter(id: string): unknown;
    loaded(): boolean;
    isMoving(): boolean;
    getMaxZoom(): number;
    project(coordinates: [number, number]): { x: number; y: number };
}
export interface EvidenceMapbox { workerCount: number; Map: new(options: object) => EvidenceMap }
export interface ViewerTrace {
    key: string | null;
    checked: boolean;
    start: number;
    mutations: number;
    firstFrameMs?: number;
    firstFrameChecked?: boolean;
    mutationsBeforeFrame?: number;
    feedbackFrameMs?: number;
}
export interface ViewerEvidence {
    map: EvidenceMap;
    mutations: number;
    sourceUpdates: number;
    sourceAdds: number;
    traces: ViewerTrace[];
    longTasks: { duration: number; start: number }[];
    workerMessages: number;
    preparationGaps?: number[];
    preparationTimer?: ReturnType<typeof setInterval>;
}
declare global { interface Window { __viewerEvidence: ViewerEvidence } }
