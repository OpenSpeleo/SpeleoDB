/**
 * Shared watchlist-page scaffolding for cylinder & sensor fleets.
 *
 * Both `cylinder_fleet/watchlist.html` and `sensor_fleet/watchlist.html`
 * render a single DataTable, a days-filter form, and an Excel-export
 * link. This helper centralizes that scaffolding.
 *
 * Usage:
 *   attachFleetWatchlist({
 *       tableSelector: '#watchlist_cylinders_table',
 *       dataTableOptions: {                 // optional overrides
 *           columnDefs: [{ targets: -1, orderable: false }],
 *       },
 *       formSelector: '#watchlist_form',    // optional (omit for pages without days filter)
 *       submitBtnSelector: '#btn_update_watchlist',
 *       daysInputSelector: '#days',
 *       exportBtnSelector: '#btn_export_excel',
 *       exportUrlBuilder: function (days) {    // called on export click
 *           return Urls['api:v2:cylinder-fleet-watchlist-export'](fleetId) + '?days=' + days;
 *       },
 *   });
 *
 * Requires: jQuery, DataTables, FormModals.
 */

/* global FormModals */
/* exported attachFleetWatchlist */

function attachFleetWatchlist(options) {
    var tableSelector = options.tableSelector;
    var dataTableOptions = Object.assign({
        paging: false,
        searching: false,
        info: false,
        order: [],
    }, options.dataTableOptions || {});

    var formSelector = options.formSelector;
    var submitBtnSelector = options.submitBtnSelector || '#btn_update_watchlist';
    var daysInputSelector = options.daysInputSelector || '#days';
    var exportBtnSelector = options.exportBtnSelector;
    var exportUrlBuilder = options.exportUrlBuilder;

    FormModals.bindAutoDismiss();

    if (tableSelector && $(tableSelector).length) {
        $(tableSelector).DataTable(dataTableOptions);
    }

    if (formSelector && $(formSelector).length) {
        $(formSelector).on('submit', function (e) {
            var days = $(daysInputSelector).val().trim();
            if (!days || parseInt(days, 10) < 0) {
                e.preventDefault();
                FormModals.showError('Please enter a valid number of days (0 or greater).');
                return false;
            }
            $(submitBtnSelector).prop('disabled', true).text('Loading...');
            return true;
        });
    }

    if (exportBtnSelector && typeof exportUrlBuilder === 'function') {
        $(exportBtnSelector).click(function (e) {
            e.preventDefault();
            var days = $(daysInputSelector).val() || '60';
            window.location.href = exportUrlBuilder(days);
        });
    }

    $('#modal_error button, #modal_success button').click(function () {
        $(this).closest('.fixed').fadeOut(200);
    });
}
