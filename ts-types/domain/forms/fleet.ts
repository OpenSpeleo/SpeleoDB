export interface FleetSettingsOptions {
    endpoint?: string;
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
export interface FleetEntityOptions {
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
    listEndpoint?: string | undefined;
    detailEndpoint?: (id: string | number) => string;
    resetForCreate?: () => void;
    populateForEdit?: ($button: JQuery<HTMLElement>) => void;
    collectPayload?: (isEdit: boolean) => unknown;
    reloadDelayMs?: number;
}
export interface SensorPayload {
    name: string;
    notes: string;
    status?: string | undefined;
}
