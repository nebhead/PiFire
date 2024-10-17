manual_current_mode = 'page_load';
manual_last_mode = '';

function manual_api_set(command) {
    $.ajax({
        url : '/api/set/' + command,
        type : 'POST',
        contentType: "application/json; charset=utf-8",
        traditional: true,
        success: function (data) {
            console.log('API Set [' + command + ']: ' + data.message);
        }
    });
};

function manual_get_status() {
    $.ajax({
        url : '/api/get/mode',
        type : 'GET',
        contentType: "application/json; charset=utf-8",
        traditional: true,
        success: function (data) {
            console.log('API Response: ' + data.message);
            manual_current_mode = data.data.mode;
            if (manual_current_mode != manual_last_mode) {
                manual_last_mode = manual_current_mode;
                if (manual_current_mode == 'Manual') {
                    $("#manual_inactive_card").hide();
                    $("#manual_active_card").show();
                    document.getElementById("manual_toggle_button").className = "btn btn-success btn-block shadow";
                    document.getElementById("manual_toggle_button").value = "on";
                    document.getElementById("manual_toggle_button").innerHTML = "Turn Off Manual Mode";
                } else {
                    $("#manual_active_card").hide();
                    $("#manual_inactive_card").show();
                    document.getElementById("manual_toggle_button").className = "btn btn-secondary btn-block shadow";
                    document.getElementById("manual_toggle_button").value = "off";
                    document.getElementById("manual_toggle_button").innerHTML = "Turn On Manual Mode";
                };
            }
        }
    });
};

// Main Loop
$(document).ready(function(){
    $("#manual_toggle_button").click(function(){
        if (document.getElementById("manual_toggle_button").value == 'off') {
            manual_api_set('mode/manual');
            console.log('Requesting Manual Mode.');
        } else {
            manual_api_set('mode/stop');
            console.log('Requesting Off Mode.');
        };
    });
    
    // Control Panel Loop
    setInterval(function(){
        manual_get_status();
    }, 500); // Update every 500ms 
});