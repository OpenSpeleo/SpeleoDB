var found = false;
const error_keys = ["error", "errors", "detail"];
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
if (!found) {
    $("#modal_error_txt").text(
        "Unknown error occured. Email: contact@speleodb.org"
    );
}
$("#modal_error").css('display', 'flex');
