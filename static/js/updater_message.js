$(document).ready(function(){
    $('#update_message_html').load('/update/post-message');
    $('#updater_message_modal').modal('show');
});

function clearMessage() {
// API Call to Clear Updater Message Flag
    var postdata = {
        "globals" : {
            "updated_message" : false
        }
    };
    $.ajax({
        url : '/api/settings',
        type : 'POST',
        data : JSON.stringify(postdata),
        contentType: "application/json; charset=utf-8",
        traditional: true,
        success: function (data) {
            console.log('Message Cleared.');
        }
    });
};