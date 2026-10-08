/** The private JSDOM hooks consumed by the Bun preload bridge only. */
export interface JsdomWindow {
    _globalProxy: object;
}

export interface JsdomWindowModule {
    createWindow(this: void, options: unknown): JsdomWindow;
}

export interface JsdomWebIdlUtilities {
    implForWrapper(this: void, wrapper: object): object | null;
    registerWrapper(this: void, wrapper: object, implementation: object | null, descriptor: object): void;
}

export interface JsdomEventTargetModule {
    interfaceDescriptor: object;
}
