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
                    error_msg += "- <b>Error:</b> `" + escapeHtml(key) + "`: ";
                    error_msg += escapeHtml(data.responseJSON["errors"][key]) + "<br>";
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

    if (!found && data.responseJSON) {
        var error_msg = "";
        for (var field_name in data.responseJSON) {
            var field_errors = data.responseJSON[field_name];

            if (Array.isArray(field_errors)) {
                error_msg += "<b>" + escapeHtml(field_name) + ":</b><br>";
                field_errors.forEach(function (err) {
                    error_msg += "- " + escapeHtml(err) + "<br>";
                });
            }
            else if (typeof field_errors === 'string') {
                error_msg += "<b>" + escapeHtml(field_name) + ":</b> " + escapeHtml(field_errors) + "<br>";
            }
            else if (typeof field_errors === 'object') {
                error_msg += "<b>" + escapeHtml(field_name) + ":</b><br>";
                for (var sub_field in field_errors) {
                    error_msg += "- " + escapeHtml(sub_field) + ": " + escapeHtml(field_errors[sub_field]) + "<br>";
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
    error_msg = `<b>[Status ${escapeHtml(data.status)}] An error occurred:</b> \`${escapeHtml(data.statusText)}\`<br>
    Please email: <a class="underline" href="mailto:contact@speleodb.org">contact@speleodb.org</a>`;
    console.error(error_msg, exception.message);
    $("#modal_error_txt").html(error_msg);
} finally {
    $("#modal_error").css('display', 'flex');
}
