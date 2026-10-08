/** Inert Django context consumed by the shared public/private map runtime. */
export interface MapRuntimeIcons {
    sensor?: string;
    biology?: string;
    bone?: string;
    artifact?: string;
    geology?: string;
    explorationLead?: string;
    cylinderOrange?: string;
}

export interface MapRuntimeContext {
    csrfToken?: string;
    mapboxToken?: string;
    viewMode?: string;
    gisToken?: string;
    allowPreciseZoom?: boolean;
    geometryColors?: string[];
    icons: Readonly<MapRuntimeIcons>;
}

/** Only gesture subscriptions are needed by the camera-intent owner. */
export interface NavigationGesture {
    originalEvent?: unknown;
}

export interface NavigationMap {
    on?(event: 'movestart', handler: (event: NavigationGesture) => void): unknown;
    off?(event: 'movestart', handler: (event: NavigationGesture) => void): unknown;
}

/** Read-only navigation needs only camera movement and optional gesture subscriptions. */
export interface ViewerNavigationMap extends NavigationMap {
    flyTo(options: { center: [number, number]; zoom: number; essential?: boolean }): unknown;
}
