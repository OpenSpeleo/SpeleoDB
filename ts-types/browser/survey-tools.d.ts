import type * as PrismRuntime from 'prismjs';

declare global {
    interface Window {
        Prism: typeof PrismRuntime;
        surveyData?: string;
    }
}
