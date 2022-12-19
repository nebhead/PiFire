// Setup Global Variables 
var mode = "Init";
var last_mode = "Init";
var splus_state = true;
var last_splus_state = false; 
var pwm_control = false;
var last_pwm_control = false;
var primary_setpoint = 0;
var last_primary_setpoint = -1;

// API Calls
function api_post(postdata) {
    $.ajax({
        url : '/api/control',
        type : 'POST',
        data : JSON.stringify(postdata),
        contentType: "application/json; charset=utf-8",
        traditional: true,
        success: function (data) {
            console.log('API Post Call: ' + data.control);
        }
    });
};

// General Functions 
function setPrime(prime_amount, next_mode) {
    var postdata = { 
        'updated' : true,
        'mode' : 'Prime',
        'prime_amount' : prime_amount,
        'next_mode' : next_mode	
    };
    api_post(postdata);
};

function update_mode() {
    // Update control panel buttons if mode changed
    console.log('Detected MODE change.')

    // Hide / Unhide relevant toolbar group
    if ((mode == 'Startup') || (mode == 'Reignite')) {
        // Select Inactive Group w/o Prime & Monitor Buttons
        $("#active_group").hide();
        $("#prime_group").hide();
        $("#monitor_btn").hide();
        $("#smoke_inactive_btn").show();
        $("#hold_inactive_btn").show();
        $("#inactive_group").show();
    } else if (mode == 'Monitor') {
        $("#prime_group").hide();
        $("#active_group").hide();
        $("#inactive_group").show();
    } else if ((mode == 'Smoke') || (mode == 'Hold') || (mode == 'Shutdown')) {
        // Select Active Group
        $("#inactive_group").hide(); 
        $("#active_group").show();
    } else {
        // Select Inactive Group w/Prime & Monitor Buttons
        $("#active_group").hide();
        $("#smoke_inactive_btn").hide();
        $("#hold_inactive_btn").hide();
        $("#monitor_btn").show();
        $("#prime_group").show();
        $("#inactive_group").show();
    };

    // Highlight Active Mode Button 
    if((mode == 'Startup') || (mode == 'Reignite')) {
        document.getElementById("startup_btn").className = "btn btn-success border border-secondary";
    } else if (mode == 'Monitor') {
        document.getElementById("monitor_btn").className = "btn btn-secondary border border-secondary";
    } else if (mode == 'Smoke') {
        document.getElementById("smoke_active_btn").className = "btn btn-warning border border-secondary";
    } else if (mode == 'Hold') {
        document.getElementById("hold_active_btn").className = "btn btn-primary border border-secondary text-white";
        $("#hold_active_btn").html(primary_setpoint + "°" + units);
    } else if (mode == 'Shutdown') {
        document.getElementById("shutdown_active_btn").className = "btn btn-danger border border-secondary";
    } else if (mode == 'Stop') {
        document.getElementById("stop_inactive_btn").className = "btn btn-danger border border-secondary";
    } else if (mode == 'Prime') {
        document.getElementById("prime_btn").className = "btn btn-primary border border-secondary dropdown-toggle text-white";
    } else if (mode == 'Error') {
        $("#error_group").show();
    };

    // Dim Last Mode Button 
    if((last_mode == 'Startup') || (last_mode == 'Reignite')) {
        document.getElementById("startup_btn").className = "btn btn-outline-secondary border border-secondary";
    } else if (last_mode == 'Monitor') {
        document.getElementById("monitor_btn").className = "btn btn-outline-secondary border border-secondary";
    } else if (last_mode == 'Smoke') {
        document.getElementById("smoke_active_btn").className = "btn btn-outline-secondary border border-secondary";
    } else if (last_mode == 'Hold') {
        document.getElementById("hold_active_btn").className = "btn btn-outline-secondary border border-secondary";
        $("#hold_active_btn").html("<i class=\"fas fa-crosshairs\"></i>");
    } else if (last_mode == 'Shutdown') {
        document.getElementById("shutdown_active_btn").className = "btn btn-outline-secondary border border-secondary";
    } else if (last_mode == 'Stop') {
        document.getElementById("stop_inactive_btn").className = "btn btn-outline-secondary border border-secondary";
    } else if (last_mode == 'Prime') {
        document.getElementById("prime_btn").className = "btn btn-outline-primary border border-secondary dropdown-toggle";
    } else if (last_mode == 'Error') {
        $("#error_group").hide();
    };

    // Reset last_mode to current_mode
    last_mode = mode;
};

function update_splus() {
    // Update splus buttons if splus_state changed
    console.log('Detected SPLUS change.')

    if ((mode == 'Smoke') || (mode == 'Hold')) {
        console.log('** Updating SPLUS. **')
        if (splus_state == true) {
            $("#splus_btn").show();
            document.getElementById("splus_btn").className = "btn btn-success border border-secondary shadow";
        } else {
            $("#splus_btn").show();
            document.getElementById("splus_btn").className = "btn btn-outline-primary border border-secondary text-secondary shadow";
        };
    };

    last_splus_state = splus_state;
};

function update_setpoint() {
    // Update Primary Setpoint if it has changed
    console.log('Detected Primary SETPOINT change.')

    if (mode == 'Hold') {
        $("#hold_active_btn").html(primary_setpoint + "°" + units);
    } else {
        $("#hold_active_btn").html("<i class=\"fas fa-crosshairs\"></i>");
    };

    last_primary_setpoint = primary_setpoint;
};

function update_pwm() {
    // Update PWM button if pwm_control changed
    console.log('Detected PWM change.')

    if (mode == 'Hold') {
        if (pwm_control == true) {
            $("#pwm_control_btn").show();
            document.getElementById("pwm_control_btn").className = "btn btn-success border border-secondary";
        } else {
            $("#pwm_control_btn").show();
            document.getElementById("pwm_control_btn").className = "btn btn-outline-primary border border-secondary text-secondary";
        };
    } else {
        $("#pwm_control_btn").hide();
    };
    last_pwm_control = pwm_control;
};

function check_state() {
    // Get control data and update control panel if needed
    $.ajax({
        url : '/api/control',
        type : 'GET',
        success : function (control) {
            // Relevant data returned from call:
            //  data.mode
            //  data.splus
            //  data.pwm_control
            //  data.primary_setpoint
            
            mode = control.control.mode;
            splus_state = control.control.s_plus;
            pwm_control = control.control.pwm_control;
            primary_setpoint = control.control.primary_setpoint;

            if(mode != last_mode) {
                update_mode();
            };
            if(splus_state != last_splus_state) {
                update_splus();
            };
            if(pwm_control != last_pwm_control) {
                update_pwm();
            };
            if(primary_setpoint != last_primary_setpoint) {
                update_setpoint();
            };
        }
    });
};

// Main Loop

$(document).ready(function(){
    // Setup Button Listeners
    $("#startup_btn").click(function(){
        var postdata = { 
            'updated' : true,
            'mode' : 'Startup'	
        };
        console.log('Requesting Startup.');
        api_post(postdata);
    });

    $("#monitor_btn").click(function(){
        var postdata = { 
            'updated' : true,
            'mode' : 'Monitor'	
        };
        console.log('Requesting Monitor.');
        api_post(postdata);
    });

    $("#shutdown_active_btn").click(function(){
        var postdata = { 
            'updated' : true,
            'mode' : 'Shutdown'	
        };
        console.log('Requesting Shutdown.');
        api_post(postdata);
    });

    $("#stop_active_btn, #stop_inactive_btn").click(function(){
        var postdata = { 
            'updated' : true,
            'mode' : 'Stop'	
        };
        console.log('Requesting Stop.');
        api_post(postdata);
    });

    $("#smoke_inactive_btn, #smoke_active_btn").click(function(){
        var postdata = { 
            'updated' : true,
            'mode' : 'Smoke'
            //'s_plus' : splusDefault
        };
        console.log('Requesting Smoke.');
        api_post(postdata);
    });

    $("#splus_btn").click(function(){
        // Toggle based on current value of this button
        if(splus_state == true) {
            var postdata = { 's_plus' : false };
            console.log('splus_state = ' + splus_state + ' Requesting false.');
        } else {
            var postdata = { 's_plus' : true };
            console.log('splus_state = ' + splus_state + ' Requesting true.');
        };
        api_post(postdata);
    });

    $("#pwm_control_btn").click(function(){
        // Toggle based on current value of this button
        if(pwm_control == true) {
            var postdata = { 'pwm_control' : false };
            console.log('pwm_control_state = ' + pwm_control + ' Requesting false.');
        } else {
            var postdata = { 'pwm_control' : true };
            console.log('pwm_control_state = ' + pwm_control + ' Requesting true.');
        };
        api_post(postdata);
    });

    $("#hold_modal_btn").click(function(){
        var setPoint = parseInt($("#tempInputId").val());
        var postdata = { 
            'updated' : true,
            'mode' : 'Hold',
            //'s_plus' : splusDefault,
            'primary_setpoint' : setPoint 
        };
        console.log('Requesting Hold at: ' + setPoint);
        api_post(postdata);
    });

    // Control Panel Loop
    setInterval(function(){
        check_state();
    }, 500); // Update every 500ms 
});