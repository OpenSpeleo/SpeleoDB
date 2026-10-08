import 'jquery';

/** jQuery aborts only on false; the existing forms explicitly return true. */
type FormAjaxSettings = Omit<JQuery.AjaxSettings<unknown>, 'beforeSend'> & {
    beforeSend?: (
        this: unknown,
        xhr: JQuery.jqXHR<unknown>,
        settings: JQuery.AjaxSettings<unknown>,
    ) => boolean | void;
};

declare global {
    interface JQueryStatic {
        ajax(settings: FormAjaxSettings): JQuery.jqXHR<unknown>;
    }
}
