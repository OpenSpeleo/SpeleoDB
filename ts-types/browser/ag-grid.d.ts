export interface AgGridColumn {
    field: string;
    headerName: string;
    sortable: boolean;
    filter: boolean;
    resizable: boolean;
    minWidth: number;
    flex: number;
}
export interface AgGridOptions<Row> {
    columnDefs: AgGridColumn[];
    rowData: Row[];
    defaultColDef: { sortable: boolean; filter: boolean; resizable: boolean };
    enableCellTextSelection: boolean;
    ensureDomOrder: boolean;
    pagination: boolean;
    paginationPageSize: number;
    paginationPageSizeSelector: number[];
    animateRows: boolean;
    rowSelection: 'multiple';
}
export interface AgGridApi { destroy(): void }
export interface AgGridRuntime {
    createGrid(element: HTMLElement, options: AgGridOptions<Record<string, unknown>>): AgGridApi;
}
declare global { interface Window { agGrid: AgGridRuntime } }
