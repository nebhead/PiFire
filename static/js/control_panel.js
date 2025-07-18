// Control Panel/Tool Bar JS

// Setup Global Variables 
var cpMode = "Init";
var cpLastMode = "Init";
var splus_state = true;
var last_splus_state = false; 
var cpPWMControl = false;
var last_cpPWMControl = false;
var cp_primary_setpoint = 0;
var last_primary_setpoint = -1;
var cp_units = 'F';
var cpRecipeMode = false;
var cpRecipeStep = 0;
var cpRecipeLastStep = -1;
var cpRecipePause = false;
var cpLastRecipePause = false;
var cpRecipeTriggered = false;
var cpLastRecipeTriggered = false;
var cpRecipeStepData = {};
var cpManualModeInterval = null;
var cpOutpins = {};
var cpOutpinsLast = {};

// API Calls
function cp_api_control_post(postdata) {
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

function cp_api_settings_post(postdata) {
    $.ajax({
        url : '/api/settings',
        type : 'POST',
        data : JSON.stringify(postdata),
        contentType: "application/json; charset=utf-8",
        traditional: true,
        success: function (data) {
            console.log('API Post Call: ' + data.control);
        }
    });
};

function cp_api_set(command) {
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

// General Functions 
function setPrime(prime_amount, next_mode) {
    var postdata = { 
        'updated' : true,
        'mode' : 'Prime',
        'prime_amount' : prime_amount,
        'next_mode' : next_mode	
    };
    cp_api_control_post(postdata);
};

function update_mode() {
    // Update control panel buttons if mode changed
    console.log('Detected MODE change.')
    $('#recipe_group').hide();
    // Hide / Unhide relevant toolbar group
    if ((cpMode == 'Startup') || (cpMode == 'Reignite')) {
        // Select Inactive Group w/o Prime & Monitor Buttons
        $("#active_group").hide();
        $("#prime_group").hide();
        $("#monitor_btn").hide();
        $("#smoke_inactive_btn").show();
        $("#hold_inactive_btn").show();
        $("#inactive_group").show();
        $("#manual_group").hide();
        $("#manual_pwm_group").hide();
    } else if (cpMode == 'Monitor') {
        $("#prime_group").hide();
        $("#active_group").hide();
        $("#inactive_group").show();
        $("#manual_group").hide();
        $("#manual_pwm_group").hide();
    } else if ((cpMode == 'Smoke') || (cpMode == 'Hold') || (cpMode == 'Shutdown')) {
        // Select Active Group
        $("#inactive_group").hide(); 
        $("#active_group").show();
        $("#manual_group").hide();
        $("#manual_pwm_group").hide();
    } else if (cpMode == 'Manual') {
        $("#active_group").hide();
        $("#smoke_inactive_btn").hide();
        $("#hold_inactive_btn").hide();
        $("#monitor_btn").hide();
        $("#prime_group").hide();
        $("#inactive_group").hide();
        $("#manual_group").show();
        if (cpPWMControl == true) {
            $("#manual_pwm_group").show();
        } else {
            $("#manual_pwm_group").hide();
        };
    } else {
        // Select Inactive Group w/Prime & Monitor Buttons
        $("#active_group").hide();
        $("#smoke_inactive_btn").hide();
        $("#hold_inactive_btn").hide();
        $("#monitor_btn").show();
        $("#prime_group").show();
        $("#inactive_group").show();
        $("#manual_group").hide();
        $("#manual_pwm_group").hide();
    };

    // Highlight Active Mode Button 
    if((cpMode == 'Startup') || (cpMode == 'Reignite')) {
        document.getElementById("startup_btn").className = "btn btn-success border border-secondary";
    } else if (cpMode == 'Monitor') {
        document.getElementById("monitor_btn").className = "btn btn-secondary border border-secondary";
    } else if (cpMode == 'Smoke') {
        document.getElementById("smoke_active_btn").className = "btn btn-warning border border-secondary";
    } else if (cpMode == 'Hold') {
        document.getElementById("hold_active_btn").className = "btn btn-primary border border-secondary text-white";
        $("#hold_active_btn").html(cp_primary_setpoint + "°" + cp_units);
    } else if (cpMode == 'Shutdown') {
        document.getElementById("shutdown_active_btn").className = "btn btn-danger border border-secondary";
    } else if (cpMode == 'Stop') {
        document.getElementById("stop_inactive_btn").className = "btn btn-danger border border-secondary";
    } else if (cpMode == 'Prime') {
        document.getElementById("prime_btn").className = "btn btn-primary border border-secondary dropdown-toggle text-white";
    } else if (cpMode == 'Error') {
        $("#error_group").show();
    };

    // Dim Last Mode Button 
    if((cpLastMode == 'Startup') || (cpLastMode == 'Reignite')) {
        document.getElementById("startup_btn").className = "btn btn-outline-secondary border border-secondary";
    } else if (cpLastMode == 'Monitor') {
        document.getElementById("monitor_btn").className = "btn btn-outline-secondary border border-secondary";
    } else if (cpLastMode == 'Smoke') {
        document.getElementById("smoke_active_btn").className = "btn btn-outline-secondary border border-secondary";
    } else if (cpLastMode == 'Hold') {
        document.getElementById("hold_active_btn").className = "btn btn-outline-secondary border border-secondary";
        $("#hold_active_btn").html("<i class=\"fas fa-crosshairs\"></i>");
    } else if (cpLastMode == 'Shutdown') {
        document.getElementById("shutdown_active_btn").className = "btn btn-outline-secondary border border-secondary";
    } else if (cpLastMode == 'Stop') {
        document.getElementById("stop_inactive_btn").className = "btn btn-outline-secondary border border-secondary";
    } else if (cpLastMode == 'Prime') {
        document.getElementById("prime_btn").className = "btn btn-outline-primary border border-secondary dropdown-toggle";
    } else if (cpLastMode == 'Error') {
        $("#error_group").hide();
    };

    // Reset cpLastMode to current_mode
    cpLastMode = cpMode;

    // Setup Manual Mode Interval
    if (cpMode == 'Manual') {
        cpManualModeInterval = setInterval(check_current, 500);
    } else {
        clearInterval(cpManualModeInterval);
    };
};

function update_recipe_mode() {
    var cpRecipeModeIcon = '<i class="far fa-frown"></i>';
    // Recipe Mode Hide/Unhide relevant groups
    $("#active_group").hide();
    $("#inactive_group").hide();
    $('#recipe_group').show();
    // Update control panel buttons if step changed
    console.log('Detected MODE change.')
    $("#cp_recipe_step_btn").html("Step " + cpRecipeStep);
    // Update Mode button 
    if(['Startup', 'Reignite'].includes(cpMode)) {
        cpRecipeModeIcon = '<i class="fas fa-play"></i>';         
    } else if(cpMode == 'Prime') {
        cpRecipeModeIcon = '<i class="fas fa-angle-double-right"></i>'; 
    } else if(cpMode == 'Smoke') {
        cpRecipeModeIcon = '<i class="fas fa-cloud"></i>'; 
    } else if(cpMode == 'Hold') {
        cpRecipeModeIcon = '<i class="fas fa-crosshairs"></i>&nbsp; ' + cp_primary_setpoint + "°" + cp_units; 
    } else if(cpMode == 'Shutdown') {
        $("#cp_recipe_mode_btn").hide();
        document.getElementById("cp_recipe_shutdown_btn").className = "btn btn-info text-white";
        // Change the next step button to a 'stop' icon
        $("#cp_recipe_next_step_btn").html('<i class="fas fa-stop"></i>');
    };
    $("#cp_recipe_mode_btn").html(cpRecipeModeIcon);
    cpRecipeLastStep = cpRecipeStep;
    cpLastMode = cpMode;
};

function update_recipe_pause() {
    if (cpRecipePause && cpRecipeTriggered) {
        //$("#cp_recipe_next_step_btn").html('<i class="fas fa-step-forward"></i>');
        document.getElementById("cp_recipe_next_step_btn").className = "btn btn-info text-white glowbutton";
    } else {
        //$("#cp_recipe_next_step_btn").html('<i class="fas fa-step-forward"></i>');
        document.getElementById("cp_recipe_next_step_btn").className = "btn btn-info text-white";
    };
    cpLastRecipePause = cpRecipePause;
    cpLastRecipeTriggered = cpRecipeTriggered;
};

function update_splus() {
    // Update splus buttons if splus_state changed
    console.log('Detected SPLUS change.')

    if ((cpMode == 'Smoke') || (cpMode == 'Hold')) {
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

    if (cpMode == 'Hold') {
        $("#hold_active_btn").html(cp_primary_setpoint + "°" + cp_units);
    } else {
        $("#hold_active_btn").html("<i class=\"fas fa-crosshairs\"></i>");
    };

    last_primary_setpoint = cp_primary_setpoint;
};

function update_pwm() {
    // Update PWM button if cpPWMControl changed
    console.log('Detected PWM change.')

    if (cpMode == 'Hold') {
        if (cpPWMControl == true) {
            $("#pwm_control_btn").show();
            document.getElementById("pwm_control_btn").className = "btn btn-success border border-secondary";
        } else {
            $("#pwm_control_btn").show();
            document.getElementById("pwm_control_btn").className = "btn btn-outline-primary border border-secondary text-secondary";
        };
    } else if (cpMode == 'Manual') {
        $("#manual_pwm_group").show();
    } else {
        $("#pwm_control_btn").hide();
        $("#manual_pwm_group").hide();
    };
    last_cpPWMControl = cpPWMControl;
};

function update_manual_mode() {
    if (areObjectsDifferent(cpOutpins, cpOutpinsLast) == true) {
        cpOutpinsLast = cpOutpins;
        if (cpOutpins['power'] == true) {
            document.getElementById("cp_manual_mode_power_btn").className = "btn btn-primary";
        } else {
            document.getElementById("cp_manual_mode_power_btn").className = "btn btn-outline-primary";
        };
        if (cpOutpins['igniter'] == true) {
            document.getElementById("cp_manual_mode_igniter_btn").className = "btn btn-primary";
        } else {
            document.getElementById("cp_manual_mode_igniter_btn").className = "btn btn-outline-primary";
        };
        if (cpOutpins['auger'] == true) {
            document.getElementById("cp_manual_mode_auger_btn").className = "btn btn-primary";
        } else {
            document.getElementById("cp_manual_mode_auger_btn").className = "btn btn-outline-primary";
        };
        if (cpOutpins['fan'] == true) {
            document.getElementById("cp_manual_mode_fan_btn").className = "btn btn-primary";
        } else {
            document.getElementById("cp_manual_mode_fan_btn").className = "btn btn-outline-primary";
        };
    };
};

function areObjectsDifferent(obj1, obj2) {
    const keys1 = Object.keys(obj1);
    const keys2 = Object.keys(obj2);
  
    if (keys1.length !== keys2.length) {
      return true;
    }
  
    for (let key of keys1) {
      if (obj1[key] !== obj2[key]) {
        return true;
      }
    }
  
    return false;
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
            
            if (control.control.mode == 'Recipe') {
                cpMode = control.control.recipe.step_data.mode;
                cpRecipeStep = control.control.recipe.step;
                cpRecipeMode = true;
                cpRecipeStepData = control.control.recipe.step_data; 
                cpRecipePause = control.control.recipe.step_data.pause;
                cpRecipeTriggered = control.control.recipe.step_data.triggered;
            } else {
                cpMode = control.control.mode;
                cpRecipeStep = 0;
                cpRecipeMode = false;
            };
            
            splus_state = control.control.s_plus;
            cpPWMControl = control.control.pwm_control;
            cp_primary_setpoint = control.control.primary_setpoint;

            if((cpRecipeMode) && (cpRecipeStep != cpRecipeLastStep)) {
                update_recipe_mode();
            } else if((!cpRecipeMode) && (cpMode != cpLastMode)) {
                update_mode();
                update_pwm(); // fix bug where PWM Fan control was not showing up in hold mode
            };
            if(splus_state != last_splus_state) {
                update_splus();
            };
            if(cpPWMControl != last_cpPWMControl) {
                update_pwm();
            };
            if(cp_primary_setpoint != last_primary_setpoint) {
                update_setpoint();
            };
            if((cpRecipePause != cpLastRecipePause) || (cpRecipeTriggered != cpLastRecipeTriggered)) {
                update_recipe_pause();
            };
        }
    });
};

function check_current() {
    // Get control data and update control panel if needed
    $.ajax({
        url : '/api/current',
        type : 'GET',
        success : function (current) {
            // Relevant data returned from call:
            //  data.status.units
            cp_units = current.status.units;
            cpOutpins = current.status.outpins;
            if (cpMode == 'Manual') {
                update_manual_mode();
            };
        }
    });
};

function cpRecipeUnpause() {
    cpRecipeStepData.pause = false;
    var postdata = {
        'recipe' : {
            'step_data' : cpRecipeStepData
        }
    };
    cp_api_control_post(postdata);
    cpRecipePause = false;
    update_recipe_pause();
};

function cpStartupCheck(enable) {
    // Check if user has bypassed startup_enable
    if (enable == 'False') {
        cpStartup();
    } else {
        $('#startupModal').modal('show');
    };
};

function cpStartup() {
    $('#startupModal').modal('hide');
    var postdata = { 
        'updated' : true,
        'mode' : 'Startup'	
    };
    console.log('Requesting Startup.');
    cp_api_control_post(postdata);
};

function cpStartupHold(targetTemp) {
    var target = parseInt(targetTemp);
    console.log('Requesting Startup with Hold at: ' + target);
    var postdata = { 
        'startup' : {
            'start_to_mode' : {
                'after_startup_mode' : 'Hold',
                'start_to_hold_prompt' : true,
                'primary_setpoint' : target
            },
            }	
    };
    console.log('Requesting Startup.');
    cp_api_settings_post(postdata);
    cpStartup();
};

function cpUpdatePWM(dutyCycle) {
        cp_api_set('manual/pwm/'+dutyCycle);
        console.log('Requesting manual pwm duty cycle: ' + dutyCycle);
};

// Main Loop

$(document).ready(function(){
    check_current();
    
    // Setup Button Listeners

    $('#startupModal').on('shown.bs.modal', function (event) {
        $('#startupSlider').val(0);
    });


    $("#monitor_btn").click(function(){
        var postdata = { 
            'updated' : true,
            'mode' : 'Monitor'	
        };
        console.log('Requesting Monitor.');
        cp_api_control_post(postdata);
    });

    $("#shutdown_active_btn, #cp_recipe_shutdown_btn").click(function(){
        var postdata = { 
            'updated' : true,
            'mode' : 'Shutdown'	
        };
        console.log('Requesting Shutdown.');
        cp_api_control_post(postdata);
    });

    $("#stop_active_btn, #stop_inactive_btn").click(function(){
        var postdata = { 
            'updated' : true,
            'mode' : 'Stop'	
        };
        console.log('Requesting Stop.');
        cp_api_control_post(postdata);
    });

    $("#smoke_inactive_btn, #smoke_active_btn").click(function(){
        var postdata = { 
            'updated' : true,
            'mode' : 'Smoke'
            //'s_plus' : splusDefault
        };
        console.log('Requesting Smoke.');
        cp_api_control_post(postdata);
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
        cp_api_control_post(postdata);
    });

    $("#pwm_control_btn").click(function(){
        // Toggle based on current value of this button
        if(cpPWMControl == true) {
            var postdata = { 'pwm_control' : false };
            console.log('pwm_control_state = ' + cpPWMControl + ' Requesting false.');
        } else {
            var postdata = { 'pwm_control' : true };
            console.log('pwm_control_state = ' + cpPWMControl + ' Requesting true.');
        };
        cp_api_control_post(postdata);
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
        cp_api_control_post(postdata);
    });

    $("#cp_recipe_next_step_btn").click(function(){
        //console.log('You clicked the button!');
        if(cpRecipePause && cpRecipeTriggered) {
            // If the recipe was paused, then follow the unpause path
            console.log('Unpausing to Next Step.');
            cpRecipeUnpause();
        } else {
            // If the user is requesting next step, force next step
            console.log('Requesting Next Step.');
            var postdata = { 
                'updated' : true
            };
            cp_api_control_post(postdata);
        };
    });

    // Manual Mode Listeners
    $("#cp_manual_stop_btn").click(function(){
        var postdata = { 
            'updated' : true,
            'mode' : 'Stop'	
        };
        console.log('Requesting Manual Mode Stop.');
        cp_api_control_post(postdata);
    });

    $("#cp_manual_mode_power_btn").click(function(){
        cp_api_set('manual/power/toggle');
        console.log('Requesting manual power toggle.');
    });

    $("#cp_manual_mode_igniter_btn").click(function(){
        cp_api_set('manual/igniter/toggle');
        console.log('Requesting manual igniter toggle.');
    });

    $("#cp_manual_mode_auger_btn").click(function(){
        cp_api_set('manual/auger/toggle');
        console.log('Requesting manual auger toggle.');
    });

    $("#cp_manual_mode_fan_btn").click(function(){
        cp_api_set('manual/fan/toggle');
        console.log('Requesting manual fan toggle.');
    });

    // Control Panel Loop
    setInterval(function(){
        check_state();
    }, 500); // Update every 500ms 
});