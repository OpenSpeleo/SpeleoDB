export type ViewerUpdateStatus = 'applied' | 'superseded' | 'cancelled' | 'failed';
export interface ViewerUpdateResult { status: ViewerUpdateStatus; error?: unknown }
export interface ViewerUpdateContext {
    isCurrent(): boolean;
    yield(): Promise<boolean>;
    shouldYield(): boolean;
}
export type ViewerWork = (context: ViewerUpdateContext) => unknown;
export interface ViewerUpdateOptions { onError?: ((error: unknown) => unknown) | undefined }
export interface ViewerSchedulerOptions {
    scheduleAfterPaint?: (callback: () => void) => (() => void);
    yieldWork?: () => Promise<unknown>;
    now?: () => number;
    budget?: () => number;
}
export interface ViewerUpdateScheduler {
    schedule(key: string | object, work: ViewerWork, options?: ViewerUpdateOptions): Promise<ViewerUpdateResult>;
    cancel(key: string | object): void;
    cancelAll(): void;
    whenIdle(): Promise<void>;
}
export interface ViewerPaintGate {
    ready: boolean;
    promise: Promise<void>;
    release: () => void;
    cancel: (() => void) | null;
}
export interface ViewerUpdateJob {
    key: string | object;
    work: ViewerWork;
    onError: ViewerUpdateOptions['onError'];
    resolve: (result: ViewerUpdateResult) => void;
    settled: boolean;
    paint: ViewerPaintGate;
}
