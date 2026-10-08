import * as maplibre from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import type { RendererConstructors } from '../../../../../../ts-types/domain/renderer.ts';

// Bundle the native module worker and its shared dependencies as a Vite asset.
maplibre.setWorkerUrl(workerUrl);

/**
 * One imported engine boundary for the application's narrow renderer capabilities.
 * Domain and tool interfaces intentionally accept structural test/rendering ports;
 * the concrete MapLibre constructor retains ownership of the actual map instance.
 */
export const Renderer = maplibre as unknown as RendererConstructors;
