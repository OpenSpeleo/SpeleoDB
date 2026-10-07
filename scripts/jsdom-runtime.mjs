import { createRequire } from 'node:module';

// Bun replaces bare "undici" imports with an incomplete built-in implementation.
// JSDOM needs the installed dependency's Dispatcher API for real HTTP requests.
// Select JSDOM's declared copy through its public entrypoint, then reuse that
// module for bare imports before JSDOM loads. No networking behavior is mocked.
// Remove this alias when Bun's built-in Dispatcher supports these APIs and the
// real HTTP upload and mutex tests pass without it.
const requireFromJsdom = createRequire(import.meta.resolve('jsdom/package.json'));
const installedUndiciPath = requireFromJsdom.resolve('undici/index.js');
requireFromJsdom(installedUndiciPath);
requireFromJsdom.cache.undici = requireFromJsdom.cache[installedUndiciPath];
