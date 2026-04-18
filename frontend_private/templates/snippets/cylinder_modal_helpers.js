{% load static %}
<script>
    /* Cylinder modal helpers shared by cylinder_fleet/details.html and
       cylinder_fleet/watchlist.html. Consumed by `attachFleetEntityCrud`
       in `forms/fleet_entity_crud.js`.

       The payload shape matches the cylinder serializer
       (name/serial/brand/owner/type/notes + o2/he/pressure + unit_system
       + status + {manufactured,visual,hydro}_date + use_anode). */

    function _cylinderDateToMonth(dateStr) {
        if (!dateStr) return '';
        return dateStr.substring(0, 7);
    }
    function _cylinderMonthToDate(monthStr) {
        if (!monthStr) return null;
        return monthStr + '-01';
    }

    function cylinderResetForCreate() {
        $('#modal_cylinder_name').val('');
        $('#modal_cylinder_serial').val('');
        $('#modal_cylinder_brand').val('');
        $('#modal_cylinder_owner').val('');
        $('#modal_cylinder_type').val('');
        $('#modal_cylinder_notes').val('');
        $('#modal_cylinder_o2').val('21');
        $('#modal_cylinder_he').val('0');
        $('#modal_cylinder_pressure').val('');
        $('#modal_cylinder_unit_system').val('imperial');
        $('#modal_cylinder_status').val('functional');
        $('#modal_cylinder_manufactured_date').val('');
        $('#modal_cylinder_visual_date').val('');
        $('#modal_cylinder_hydro_date').val('');
        $('#modal_cylinder_use_anode').prop('checked', false);
    }

    function cylinderPopulateForEdit($button) {
        $('#modal_cylinder_name').val($button.data('cylinder-name') || '');
        $('#modal_cylinder_serial').val($button.data('cylinder-serial') || '');
        $('#modal_cylinder_brand').val($button.data('cylinder-brand') || '');
        $('#modal_cylinder_owner').val($button.data('cylinder-owner') || '');
        $('#modal_cylinder_type').val($button.data('cylinder-type') || '');
        $('#modal_cylinder_notes').val($button.data('cylinder-notes') || '');
        $('#modal_cylinder_o2').val($button.data('cylinder-o2') ?? '');
        $('#modal_cylinder_he').val($button.data('cylinder-he') ?? '');
        $('#modal_cylinder_pressure').val($button.data('cylinder-pressure') ?? '');
        $('#modal_cylinder_unit_system').val($button.data('cylinder-unit-system') || 'imperial');
        $('#modal_cylinder_status').val($button.data('cylinder-status') || 'functional');
        $('#modal_cylinder_manufactured_date').val(_cylinderDateToMonth($button.data('cylinder-manufactured-date')));
        $('#modal_cylinder_visual_date').val(_cylinderDateToMonth($button.data('cylinder-visual-date')));
        $('#modal_cylinder_hydro_date').val(_cylinderDateToMonth($button.data('cylinder-hydro-date')));
        $('#modal_cylinder_use_anode').prop('checked', $button.data('cylinder-use-anode') === true);
    }

    function cylinderCollectPayload() {
        var o2 = $('#modal_cylinder_o2').val();
        var he = $('#modal_cylinder_he').val();
        var pressure = $('#modal_cylinder_pressure').val();

        if (!o2 || !he || !pressure) {
            FormModals.showError('O2, He, and Pressure are required.');
            return null;
        }

        return {
            name: $('#modal_cylinder_name').val().trim(),
            serial: $('#modal_cylinder_serial').val().trim(),
            brand: $('#modal_cylinder_brand').val().trim(),
            owner: $('#modal_cylinder_owner').val().trim(),
            type: $('#modal_cylinder_type').val().trim(),
            notes: $('#modal_cylinder_notes').val().trim(),
            o2_percentage: parseInt(o2, 10),
            he_percentage: parseInt(he, 10),
            pressure: parseInt(pressure, 10),
            unit_system: $('#modal_cylinder_unit_system').val(),
            status: $('#modal_cylinder_status').val(),
            manufactured_date: _cylinderMonthToDate($('#modal_cylinder_manufactured_date').val()),
            last_visual_inspection_date: _cylinderMonthToDate($('#modal_cylinder_visual_date').val()),
            last_hydrostatic_test_date: _cylinderMonthToDate($('#modal_cylinder_hydro_date').val()),
            use_anode: $('#modal_cylinder_use_anode').is(':checked'),
        };
    }
</script>
