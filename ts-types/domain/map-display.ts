export type ColorMode = 'project' | 'depth' | 'shot';
export type DepthUnit = 'ft' | 'm';
export interface DepthDomain { min: number; max: number }
export type DisplayCategory = 'caveEntrances' | 'surveyStations' | 'surfaceStations' | 'landmarks' | 'explorationLeads' | 'cylinders';
export type DisplayStationType = 'sensor' | 'biology' | 'bone' | 'artifact' | 'geology';
export type DisplayConcern = 'projects' | 'networks' | 'categories' | 'depth' | 'colors' | 'depth-labels' | 'geometry-labels';

export interface DisplayPreferences {
    geometryLabelsVisible: boolean;
    colorMode: ColorMode;
    depthLimitFeet: number | null;
    depthUnit: DepthUnit;
    categories: Record<DisplayCategory, boolean>;
    stationTypes: Record<DisplayStationType, boolean>;
}

/** Untrusted persisted fields remain unknown until the existing field-specific checks. */
export interface StoredDisplayPreferences {
    geometryLabelsVisible?: unknown;
    version?: unknown;
    colorMode?: unknown;
    depthLimitFeet?: unknown;
    depthUnit?: unknown;
    categories?: unknown;
    stationTypes?: unknown;
}
