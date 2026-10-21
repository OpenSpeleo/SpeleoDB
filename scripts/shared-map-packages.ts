export const sharedMapResolution = {
    // Compatibility with older source-enabled revisions; npm exports default to source.
    conditions: ['speleodb-source', 'module', 'browser', 'development|production'],
    dedupe: ['maplibre-gl', '@speleodb/api', '@speleodb/map-core', '@speleodb/map-viewer'],
    preserveSymlinks: true,
};
