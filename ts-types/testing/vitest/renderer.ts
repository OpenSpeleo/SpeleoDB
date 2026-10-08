import type { RendererConstructors } from '../../domain/renderer.ts';

/** External engine double used only by the Vitest module boundary. */
declare global { var __mapRenderer: RendererConstructors; }
