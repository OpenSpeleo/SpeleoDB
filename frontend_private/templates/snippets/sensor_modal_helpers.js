{% load static %}
<script>
    /* Sensor modal helpers used by sensor_fleet/details.html. Consumed
       by `attachFleetEntityCrud` in `forms/fleet_entity_crud.js`.

       The sensor payload is simpler than the cylinder one: name +
       notes, plus `status` when editing (new sensors default to
       `functional` on the backend). The status dropdown is hidden in
       create mode and shown in edit mode. */

    function sensorResetForCreate() {
        $('#modal_sensor_name').val('');
        $('#modal_sensor_notes').val('');
        $('#modal_sensor_status').val('functional');
        $('#modal_status_container').addClass('hidden');
    }

    function sensorPopulateForEdit($button) {
        $('#modal_sensor_name').val($button.data('sensor-name') || '');
        $('#modal_sensor_notes').val($button.data('sensor-notes') || '');
        $('#modal_sensor_status').val($button.data('sensor-status') || 'functional');
        $('#modal_status_container').removeClass('hidden');
    }

    function sensorCollectPayload(isEdit) {
        var name = $('#modal_sensor_name').val().trim();
        var notes = $('#modal_sensor_notes').val().trim();
        if (!name) {
            FormModals.showError('Sensor name is required.');
            return null;
        }
        var payload = { name: name, notes: notes };
        if (isEdit) { payload.status = $('#modal_sensor_status').val(); }
        return payload;
    }
</script>
