var found = false;
const error_keys = ["error", "errors", "detail"];

try {

    for (key_idx in error_keys) {
        var key = error_keys[key_idx];
        if (key in data.responseJSON) {
            var error_value = data.responseJSON[key];
            if (key == "errors") {
                var error_msg = "";
                for (var key in error_value) {
                    error_msg += "- <b>Error:</b> `" + key + "`: ";
                    error_msg += data.responseJSON["errors"][key] + "<br>";
                }
                $("#modal_error_txt").html(error_msg);
            }
            else {
                $("#modal_error_txt").text(error_value);
            }
            found = true;
            break;
        }
    }

    // If standard error keys not found, check for field-specific validation errors
    if (!found && data.responseJSON) {
        var error_msg = "";
        for (var field_name in data.responseJSON) {
            var field_errors = data.responseJSON[field_name];

            // Handle array of error messages
            if (Array.isArray(field_errors)) {
                error_msg += "<b>" + field_name + ":</b><br>";
                field_errors.forEach(function (err) {
                    error_msg += "- " + err + "<br>";
                });
            }
            // Handle single error message
            else if (typeof field_errors === 'string') {
                error_msg += "<b>" + field_name + ":</b> " + field_errors + "<br>";
            }
            // Handle nested error objects
            else if (typeof field_errors === 'object') {
                error_msg += "<b>" + field_name + ":</b><br>";
                for (var sub_field in field_errors) {
                    error_msg += "- " + sub_field + ": " + field_errors[sub_field] + "<br>";
                }
            }
        }

        if (error_msg) {
            $("#modal_error_txt").html(error_msg);
            found = true;
        }
    }

    if (!found) {
        throw new Error("No Error Key Found");
    }
} catch (exception) {
    error_msg = `<b>[Status ${data.status}] An error occurred:</b> \`${data.statusText}\`<br>
    Please email: <a class="underline" href="mailto:contact@speleodb.org">contact@speleodb.org</a>`;
    console.error(error_msg, exception.message);
    $("#modal_error_txt").html(error_msg);
} finally {
    // Code that will run regardless of success or error
    $("#modal_error").css('display', 'flex');
}


