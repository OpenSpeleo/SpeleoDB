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

// Bun's DONT_CONTEXTIFY context and its exposed global proxy are distinct.
// JSDOM 30 registers private WebIDL fields on the context only, so register the
// proxy with the same implementation before parsing or evaluating any scripts.
// Keep the original brand checks and event implementation; remove this bridge
// when Bun exposes the same object and the window event regression tests pass.
if (process.versions.bun) {
    const windowModule = requireFromJsdom('./lib/jsdom/browser/Window.js');
    const { implForWrapper, registerWrapper } = requireFromJsdom('./lib/generated/idl/utils.js');
    const { interfaceDescriptor } = requireFromJsdom('./lib/generated/idl/EventTarget.js');
    const createWindow = windowModule.createWindow;

    windowModule.createWindow = options => {
        const window = createWindow(options);
        const proxy = window._globalProxy;
        if (proxy !== window && implForWrapper(proxy) === null) {
            registerWrapper(proxy, implForWrapper(window), interfaceDescriptor);
        }
        return window;
    };
}
