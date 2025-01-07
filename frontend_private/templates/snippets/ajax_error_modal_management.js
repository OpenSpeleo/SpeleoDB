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
    if (!found) {
        throw new Error("No Error Key Found");
    }
} catch (exception) {
    console.log("Hemlo 1");
    error_msg = `<b>[Status ${data.status}] An error occurred:</b> \`${data.statusText}\`<br>
    Please email: <a class="underline" href="mailto:contact@speleodb.org">contact@speleodb.org</a>`;
    console.log("Hemlo 2");
    console.error(error_msg, exception.message);
    console.log("Hemlo 3");
    $("#modal_error_txt").html(error_msg);
    console.log("Hemlo 4");
} finally {
    // Code that will run regardless of success or error
    $("#modal_error").css('display', 'flex');
}


