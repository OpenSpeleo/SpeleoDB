export interface FleetSettingsOptions {
    save: (payload: { name: string; description: string }) => Promise<unknown>;
    successMessage?: string | undefined;
    reloadDelayMs?: number;
    submitBtnSelector?: string;
    nameSelector?: string;
    descSelector?: string;
}
export interface FleetWatchlistOptions {
    tableSelector?: string;
    dataTableOptions?: DataTableOptions;
    formSelector?: string | undefined;
    submitBtnSelector?: string;
    daysInputSelector?: string;
    exportBtnSelector?: string | undefined;
    exportUrlBuilder?: ((days: string) => string) | undefined;
}
export interface FleetEntityOptions<Payload = unknown> {
    entityLabel?: string;
    modalSelector?: string;
    deleteModalSelector?: string | undefined;
    editButtonSelector?: string;
    deleteButtonSelector?: string | undefined;
    deleteIdInputSelector?: string | undefined;
    addButtonSelector?: string | undefined;
    saveButtonSelector?: string;
    cancelSelectors?: string;
    deleteCancelSelectors?: string | undefined;
    confirmDeleteSelector?: string | undefined;
    modalTitleSelector?: string;
    addTitle?: string;
    editTitle?: string;
    create?: ((payload: Payload) => Promise<unknown>) | undefined;
    update: (id: string | number, payload: Payload) => Promise<unknown>;
    remove?: ((id: string | number) => Promise<unknown>) | undefined;
    resetForCreate?: () => void;
    populateForEdit?: ($button: JQuery<HTMLElement>) => void;
    collectPayload?: (isEdit: boolean) => Payload | null;
    reloadDelayMs?: number;
}
