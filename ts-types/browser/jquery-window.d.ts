import 'jquery';
declare global {
    interface Window { $?: JQueryStatic | undefined }
}
export {};
