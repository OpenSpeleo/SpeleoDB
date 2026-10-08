import type { ImportGlobFunction } from 'vite/types/importGlob.d.ts';

// Import only the used glob contract: Bun and Vite own different env/hot ambients.
declare global { interface ImportMeta { glob: ImportGlobFunction } }
