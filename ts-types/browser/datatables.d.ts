/** The existing DataTables vendor owns execution; this describes consumed options. */
interface DataTableOptions {
    paging?: boolean;
    ordering?: boolean;
    searching?: boolean;
    info?: boolean;
    order?: Array<[number, 'asc' | 'desc']>;
    columnDefs?: Array<{ targets: number | number[]; orderable?: boolean; searchable?: boolean }>;
}
interface DataTableApi {
    on(event: 'draw', handler: () => void): DataTableApi;
}
interface JQuery {
    DataTable(options: DataTableOptions): DataTableApi;
}
