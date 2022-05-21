// Dashboard Control

function updateCards(data, init) {
        // Setup Dash Cards for Probe Temperatures

		// *************************  
		// Grill Temperature Card 
		// *************************  
		if(data.cur_probe_temps[0] < 0) {
			// if negative temperature, then don't display circle temp bar
			var grillPercent = 0;
		} else if(units == 'F'){
			// if units are F, adjust circle temp bar where max is 600F
			var grillPercent = ((data.cur_probe_temps[0] * 100) / 600);
		} else {
			// if units are C, adjust circle temp bar where max is 300C
			var grillPercent = ((data.cur_probe_temps[0] * 100) / 300);
		};
		if (init) {
			GrillTempCircle = circliful.newCircle({
				percent: grillPercent,
				id: 'GrillTempCircle',
				type: 'simple',
				foregroundCircleWidth: 10,
				startAngle: -180,
				backgroundCircleWidth: 10,
				text: data.cur_probe_temps[0] + "°" + units,
				textReplacesPercentage: true,
					strokeLinecap: "round",
			});
		} else {
			GrillTempCircle.update([
				{ type: "percent", value: grillPercent },
				{ type: "text", value: data.cur_probe_temps[0] + "°" + units }
			]);
		}
		// Change the notification label depending on state
		if(data.notify_req['grill']) { 
            // If notify request is active, change the button highlighting
            document.getElementById("grill_notify_btn").className = "btn btn-primary";
            // Change the text to indicate setpoint
			$("#grill_notify_btn").html("<i class=\"fas fa-bell\"></i> " + data.set_points['grill'] + "°" + units);
        } else {
            // If notify request is not active, change the button highlighting
            document.getElementById("grill_notify_btn").className = "btn btn-outline-primary";
            // Change the text to show bell with slash
			$("#grill_notify_btn").html("<i class=\"far fa-bell-slash\"></i>");
        };
		
		// *************************  
		// Probe 1 Temperature Card 
		// *************************  
		var probe1_temp = 0;
		var probe1_text = 'OFF';
        
		if(data.probes_enabled[1] == 1) {
            probe1_temp = data.cur_probe_temps[1];
            probe1_text = probe1_temp + "°" + units;
            if(data.notify_req['probe1']) { 
                // If notify request is active, change the button highlighting
                document.getElementById("probe1_notify_btn").className = "btn btn-primary";
                // Change the text to indicate setpoint
				$("#probe1_notify_btn").html("<i class=\"fas fa-bell\"></i> " + data.set_points['probe1'] + "°" + units);
            } else {
                // If notify request is not active, change the button highlighting
                document.getElementById("probe1_notify_btn").className = "btn btn-outline-primary";
                // Change the text to show bell with slash
				$("#probe1_notify_btn").html("<i class=\"far fa-bell-slash\"></i>");
            };
        };
		
		if(probe1_temp < 0) {
			// if negative temperature, then don't display circle temp bar
			var probe1Percent = 0;
		} else if(units == 'F'){
			// if units are F, adjust circle temp bar where max is 300F
			var probe1Percent = ((probe1_temp * 100) / 300);
		} else {
			// if units are C, adjust circle temp bar where max is 150C
			var probe1Percent = ((probe1_temp * 100) / 150);
		};

		if (init) {
			Probe1TempCircle = circliful.newCircle({
				percent: probe1Percent,
				id: 'Probe1TempCircle',
				type: 'simple',
				foregroundCircleWidth: 10,
				startAngle: -180,
				backgroundCircleWidth: 10,
				text: probe1_text,
				textReplacesPercentage: true,
					strokeLinecap: "round",
			});
		} else if (data.probes_enabled[1] == 1) {
			Probe1TempCircle.update([
				{ type: "percent", value: probe1Percent },
				{ type: "text", value: data.cur_probe_temps[1] + "°" + units }
			]);
		} else {
			Probe1TempCircle.update([
				{ type: "percent", value: 0 },
				{ type: "text", value: "OFF" }
			]);
		};

		// *************************  
		// Probe 1 Temperature Card 
		// *************************  
		var probe2_temp = 0;
		var probe2_text = 'OFF';

		if(data.probes_enabled[2] == 1) {
            probe2_temp = data.cur_probe_temps[2];
            probe2_text = probe2_temp + "°" + units;
            if(data.notify_req['probe2']) { 
                // If notify request is active, change the button highlighting
                document.getElementById("probe2_notify_btn").className = "btn btn-primary";
                // Change the text to indicate setpoint
				$("#probe2_notify_btn").html("<i class=\"fas fa-bell\"></i> " + data.set_points['probe2'] + "°" + units);
            } else {
                // If notify request is not active, change the button highlighting
                document.getElementById("probe2_notify_btn").className = "btn btn-outline-primary";
                // Change the text to show bell with slash
				$("#probe2_notify_btn").html("<i class=\"far fa-bell-slash\"></i>");
            };
        };
		
		if(probe2_temp < 0) {
			// if negative temperature, then don't display circle temp bar
			var probe2Percent = 0;
		} else if(units == 'F'){
			// if units are F, adjust circle temp bar where max is 300F
			var probe2Percent = ((probe2_temp * 100) / 300);
		} else {
			// if units are C, adjust circle temp bar where max is 150C
			var probe2Percent = ((probe2_temp * 100) / 150);
		};

		if (init) {
			Probe2TempCircle = circliful.newCircle({
				percent: probe2Percent,
				id: 'Probe2TempCircle',
				type: 'simple',
				foregroundCircleWidth: 10,
				startAngle: -180,
				backgroundCircleWidth: 10,
				text: probe2_text,
				textReplacesPercentage: true,
					strokeLinecap: "round",
			});
		} else if (data.probes_enabled[2] == 1) {
			Probe2TempCircle.update([
				{ type: "percent", value: probe2Percent },
				{ type: "text", value: data.cur_probe_temps[2] + "°" + units }
			]);
		} else {
			Probe2TempCircle.update([
				{ type: "percent", value: 0 },
				{ type: "text", value: "OFF" }
			]);
		};

};

function updateHopperStatus(data) {
	if (data.hopper_level > 70) { 
		document.getElementById("HopperStatus").className = "btn btn-outline-success btn-block shadow";
	} else if (data.hopper_level > 30) {
		document.getElementById("HopperStatus").className = "btn btn-outline-warning btn-block shadow";
	} else {
		document.getElementById("HopperStatus").className = "btn btn-outline-danger btn-block shadow";
	};

	$("#HopperLevel").html(data.hopper_level);
	$("#PelletName").html(data.cur_pellets);
};

function updateDashButtons(data) {
        // Setup Dash Buttons
        if (data.current_mode == "Stop") {
            document.getElementById("stop_inactive_btn").className = "btn btn-danger border border-secondary";
            $("#active_group").hide();
			$("#splus_btn").hide();
            $("#smoke_inactive_btn").hide();
            $("#hold_inactive_btn").hide();
            $("#inactive_group").show();
			$("#monitor_btn").show();
			$("#error_btn").hide();
        } else if (data.current_mode == 'Monitor') {
            document.getElementById("monitor_btn").className = "btn btn-secondary border border-secondary";
            $("#active_group").hide();
			$("#splus_btn").hide();
            $("#inactive_group").show();
            $("#smoke_inactive_btn").hide();
            $("#hold_inactive_btn").hide();
            $("#error_btn").hide();
        } else if ((data.current_mode == 'Startup') || (data.current_mode == 'Reignite')) {
            document.getElementById("startup_btn").className = "btn btn-success border border-secondary";
            $("#active_group").hide();
			$("#splus_btn").hide();
			$("#inactive_group").show();
			$("#smoke_inactive_btn").show();
			$("#hold_inactive_btn").show();
			$("#monitor_btn").hide();
			$("#error_btn").hide();
        } else if (data.current_mode == 'Smoke') {
            document.getElementById("smoke_btn").className = "btn btn-warning border border-secondary";
            $("#inactive_group").hide();
            $("#active_group").show();
            $("#stop_btn").hide();
			$("#splus_btn").show();
			// This is required when automatically transitioning from another mode to this mode
			if(data.splus == true) {
				document.getElementById("splus_btn").className = "btn btn-success border border-secondary";
			} else {
				document.getElementById("splus_btn").className = "btn btn-outline-primary border border-secondary text-secondary";
			};
            $("#error_btn").hide();
        } else if (data.current_mode == 'Hold') {
            document.getElementById("hold_btn").className = "btn btn-secondary border border-secondary text-white";
			$("#hold_btn").html(data.set_points['grill'] + "°" + units);

            $("#inactive_group").hide();
            $("#active_group").show();
            $("#stop_btn").hide();
            $("#error_btn").hide();
			$("#splus_btn").show();
			// This is required when automatically transitioning from another mode to this mode
			if(data.splus == true) {
				document.getElementById("splus_btn").className = "btn btn-success border border-secondary";
				//document.getElementById("splus_btn").value = "false";
				$("#splus_btn").val("false");
			} else {
				document.getElementById("splus_btn").className = "btn btn-outline-primary border border-secondary text-secondary";
				//document.getElementById("splus_btn").value = "true";
				$("#splus_btn").val("true");
			};
			document.getElementById("hold_btn").className = "btn btn-secondary border border-secondary text-white";
			$("#hold_btn").html(data.set_points['grill'] + "°" + units);
        } else if (data.current_mode == 'Shutdown') {
			$("#inactive_group").hide();
			$("#splus_btn").hide();
			$("#active_group").show();
			$("#stop_btn").show();
			$("#error_btn").hide();
			document.getElementById("shutdown_btn").className = "btn btn-danger border border-secondary";
        } else if (data.current_mode == 'Error') {
			document.getElementById("stop_inactive_btn").className = "btn btn-danger border border-secondary";
			$("#active_group").hide();
			$("#splus_btn").hide();
			$("#smoke_inactive_btn").hide();
			$("#hold_inactive_btn").hide();
			$("#inactive_group").show();
			$("#monitor_btn").show();
			$("#error_btn").show();
			document.getElementById("error_btn").className = "btn btn-danger border border-warning text-warning";
		} else if (data.current_mode == 'Manual') {
			$("#active_group").hide();
			$("#inactive_group").hide();
			$("#splus_btn").hide();
			$("#smoke_inactive_btn").hide();
			$("#hold_inactive_btn").hide();
			$("#monitor_btn").hide();
			$("#error_btn").hide();
		};

        if ((data.current_mode == 'Smoke') || (data.current_mode == 'Hold')) {
            if(data.splus == true) {
                $("#splus_btn").show();
                document.getElementById("splus_btn").className = "btn btn-success border border-secondary";
            } else {
                $("#splus_btn").show();
                document.getElementById("splus_btn").className = "btn btn-outline-primary border border-secondary text-secondary";
            };
        } else {
            $("#splus_btn").hide();
        };
};

var splusState = true;
var splusDefault = true;
var last_mode = "Stop";

$(document).ready(function(){
    // Get Intial Dash Data
    req = $.ajax({
        url : '/dashdata',
        type : 'GET'
    });

    req.done(function(data) {
        // Setup Initial Dash Data
        // Data Returned From Call
        //  data.cur_probe_temps[]
        //  data.probes_enabled[]
        //  data.current_mode
        //  data.notify_req
        //  data.splus
		var init = true;
		last_mode = data.current_mode;
        splusState = data.splus;
		splusDefault = data.splus_default;
		last_grill_setpoint = data.set_points['grill'];

		updateCards(data, init);

		updateDashButtons(data); 

		init = false;  // Finished with init.

        setInterval(function(){
            // Get Dash Data
            req = $.ajax({
                url : '/dashdata',
                type : 'GET'
            });
    
            req.done(function(data) {
				// Update Cards
				updateCards(data);

                // Update dock buttons if mode changed
                if((data.current_mode != last_mode) || (data.splus != splusState)){
					// Dim relavant button for last_mode
                    if(last_mode == 'Startup') {
                        document.getElementById("startup_btn").className = "btn btn-outline-success border border-secondary";
                    } else if (last_mode == 'Monitor') {
                        document.getElementById("monitor_btn").className = "btn btn-outline-secondary border border-secondary";
                    } else if (last_mode == 'Smoke') {
                        document.getElementById("smoke_btn").className = "btn btn-outline-warning border border-secondary text-secondary";
                    } else if (last_mode == 'Hold') {
                        document.getElementById("hold_btn").className = "btn btn-outline-secondary border border-secondary";
						$("#hold_btn").html("<i class=\"fas fa-crosshairs\"></i>");
                    } else if (last_mode == 'Shutdown') {
                        document.getElementById("shutdown_btn").className = "btn btn-outline-danger border border-secondary";
                    } else if (last_mode == 'Stop') {
                        document.getElementById("stop_inactive_btn").className = "btn btn-outline-secondary border border-secondary";
                    };
                    // Reset last_mode to current_mode
                    last_mode = data.current_mode;
					splusState = data.splus;
					splusDefault = data.splus_default;
					updateDashButtons(data);
				};
				if((data.current_mode == 'Hold') && (data.set_points['grill'] != last_grill_setpoint)) {
					console.log('Update hold temp.')
					$("#hold_btn").html(data.set_points['grill'] + "°" + units);
					last_grill_setpoint = data.set_points['grill'];
				}; 

            });
        }, 1000); // Update every 1 second 
    });

    // Get Hopper Level on Page Load
    req = $.ajax({
        url : '/hopperlevel',
        type : 'GET'
    });

    req.done(function(data) {
        // Update Hopper Level
		updateHopperStatus(data);
    });

    setInterval(function(){
        // Get Hopper Level every 2.5 minutes
        req = $.ajax({
            url : '/hopperlevel',
            type : 'GET'
        });

        req.done(function(data) {
            // Update Hopper Level 
			updateHopperStatus(data);
        });
    }, 150000);

	// ******************
	// Button Listeners
	// ******************

	$("#startup_btn").click(function(){
		var postdata = { 
			'updated' : true,
			'mode' : 'Startup'	
		};
		req = $.ajax({
			url : '/api/control',
			type : 'POST',
			data : JSON.stringify(postdata),
			contentType: "application/json; charset=utf-8",
            traditional: true,
            success: function (data) {
                console.log('Startup Mode Requested.');
            }
		});
	});

	$("#monitor_btn").click(function(){
		var postdata = { 
			'updated' : true,
			'mode' : 'Monitor'	
		};
		req = $.ajax({
			url : '/api/control',
			type : 'POST',
			data : JSON.stringify(postdata),
			contentType: "application/json; charset=utf-8",
            traditional: true,
            success: function (data) {
                console.log('Monitor Mode Requested.');
            }
		});
	});

	$("#shutdown_btn").click(function(){
		var postdata = { 
			'updated' : true,
			'mode' : 'Shutdown'	
		};
		req = $.ajax({
			url : '/api/control',
			type : 'POST',
			data : JSON.stringify(postdata),
			contentType: "application/json; charset=utf-8",
            traditional: true,
            success: function (data) {
                console.log('Shutdown Mode Requested.');
            }
		});
	});

	$("#stop_btn, #stop_inactive_btn").click(function(){
		var postdata = { 
			'updated' : true,
			'mode' : 'Stop'	
		};
		req = $.ajax({
			url : '/api/control',
			type : 'POST',
			data : JSON.stringify(postdata),
			contentType: "application/json; charset=utf-8",
            traditional: true,
            success: function (data) {
                console.log('Stop Mode Requested.');
            }
		});
	});

	$("#smoke_btn, #smoke_inactive_btn").click(function(){
		var postdata = { 
			'updated' : true,
			'mode' : 'Smoke',
			's_plus' : splusDefault
		};
		req = $.ajax({
			url : '/api/control',
			type : 'POST',
			data : JSON.stringify(postdata),
			contentType: "application/json; charset=utf-8",
            traditional: true,
            success: function (data) {
                console.log('Smoke Mode Requested.');
            }
		});
	});

	$("#splus_btn").click(function(){
		// Toggle based on current value of this button
		if(splusState == true) {
			var postdata = { 's_plus' : false };
			console.log('splusState = ' + splusState + ' Requesting false.');
		} else {
			var postdata = { 's_plus' : true };
			console.log('splusState = ' + splusState + ' Requesting true.');
		};
		req = $.ajax({
			url : '/api/control',
			type : 'POST',
			data : JSON.stringify(postdata),
			contentType: "application/json; charset=utf-8",
            traditional: true,
            success: function (data) {
                console.log('Smoke Plus Toggle Requested.');
            }
		});
	});

	$("#hold_modal_btn").click(function(){
		var setPoint = parseInt($("#tempInputId").val());
		var postdata = { 
			'updated' : true,
			'mode' : 'Hold',
			's_plus' : splusDefault,
			'setpoints' : {
				'grill' : setPoint 
			}	
		};
		req = $.ajax({
			url : '/api/control',
			type : 'POST',
			data : JSON.stringify(postdata),
			contentType: "application/json; charset=utf-8",
            traditional: true,
            success: function (data) {
                console.log('Hold Mode Requested. ' + setPoint + units);
				$("#hold_btn").html(setPoint + "°" + units);
            }
		});
	});

	$("#grill_notify_enable").click(function(){
		var setPoint = parseInt($("#grilltempInputId").val());
		var updated = false;
		if(last_mode == "Hold") {
			updated = true;
			// Update the new setpoint
			$("#hold_btn").html(setPoint + "°" + units);
		}

		var postdata = { 
			'setpoints' : {
				'grill' : setPoint 
			},
			'notify_req' : {
				'grill' : true
			},
			'updated' : updated
		};
		req = $.ajax({
			url : '/api/control',
			type : 'POST',
			data : JSON.stringify(postdata),
			contentType: "application/json; charset=utf-8",
            traditional: true,
            success: function (data) {
                console.log('Notification for Grill Requested.');
            }
		});
	});

	$("#grill_notify_disable").click(function(){
		var postdata = {
			'setpoints' : {
				'grill' : 0
			},
			'notify_req' : {
				'grill' : false
			}
		};
		req = $.ajax({
			url : '/api/control',
			type : 'POST',
			data : JSON.stringify(postdata),
			contentType: "application/json; charset=utf-8",
            traditional: true,
            success: function (data) {
                console.log('Notification for Grill Cancelled.');
            }
		});
	});

	$("#p1_notify_enable").click(function(){
		var setPoint = parseInt($("#probe1tempInputId").val());
		var shutdown = false;
		var keepWarm = false;
		if ($('#shutdownP1').is(":checked")){
			shutdown = true;
		};
		if ($('#keepWarmP1').is(":checked")){
			keepWarm = true;
		};
		var postdata = { 
			'setpoints' : {
				'probe1' : setPoint 
			},
			'notify_req' : {
				'probe1' : true
			},
			'notify_data' : {
				'p1_shutdown' : shutdown,
				'p1_keep_warm' : keepWarm
			} 	
		};
		req = $.ajax({
			url : '/api/control',
			type : 'POST',
			data : JSON.stringify(postdata),
			contentType: "application/json; charset=utf-8",
            traditional: true,
            success: function (data) {
                console.log('Notification for Probe 1 Requested. Shutdown = ' + shutdown + ' Keep Warm = ' + keepWarm);
            }
		});
	});

	$("#p1_notify_disable").click(function(){
		var postdata = {
			'setpoints' : {
				'probe1' : 0
			},
			'notify_req' : {
				'probe1' : false
			},
			'notify_data' : {
				'p1_shutdown' : false,
				'p1_keep_warm' : false
			} 	
		};
		req = $.ajax({
			url : '/api/control',
			type : 'POST',
			data : JSON.stringify(postdata),
			contentType: "application/json; charset=utf-8",
            traditional: true,
            success: function (data) {
                console.log('Notification for Probe 1 Cancelled.');
            }
		});
	});

	$("#p2_notify_enable").click(function(){
		var setPoint = parseInt($("#probe2tempInputId").val());
		var shutdown = false;
		var keepWarm = false;
		if ($('#shutdownP2').is(":checked")){
			shutdown = true;
		};
		if ($('#keepWarmP2').is(":checked")){
			keepWarm = true;
		};
		var postdata = { 
			'setpoints' : {
				'probe2' : setPoint 
			},
			'notify_req' : {
				'probe2' : true
			},
			'notify_data' : {
				'p2_shutdown' : shutdown,
				'p2_keep_warm' : keepWarm
			} 	
		};
		req = $.ajax({
			url : '/api/control',
			type : 'POST',
			data : JSON.stringify(postdata),
			contentType: "application/json; charset=utf-8",
            traditional: true,
            success: function (data) {
                console.log('Notification for Probe 2 Requested. Shutdown = ' + shutdown + ' Keep Warm = ' + keepWarm);
            }
		});
	});

	$("#p2_notify_disable").click(function(){
		var postdata = {
			'setpoints' : {
				'probe2' : 0
			},
			'notify_req' : {
				'probe2' : false
			},
			'notify_data' : {
				'p2_shutdown' : false,
				'p2_keep_warm' : false
			} 	
		};
		req = $.ajax({
			url : '/api/control',
			type : 'POST',
			data : JSON.stringify(postdata),
			contentType: "application/json; charset=utf-8",
            traditional: true,
            success: function (data) {
                console.log('Notification for Probe 2 Cancelled.');
            }
		});
	});

	// ******************
	// Checkbox Listeners
	// ******************

	$("#shutdownP1").click(function(){
		if($(this).is(':checked')){
			document.getElementById("keepWarmP1").disabled = true;
		} else {
			document.getElementById("keepWarmP1").disabled = false;
		}
	});

	$("#keepWarmP1").click(function(){
		if($(this).is(':checked')){
			document.getElementById("shutdownP1").disabled = true;
		} else {
			document.getElementById("shutdownP1").disabled = false;
		}
	});

	$("#shutdownP2").click(function(){
		if($(this).is(':checked')){
			document.getElementById("keepWarmP2").disabled = true;
		} else {
			document.getElementById("keepWarmP2").disabled = false;
		}
	});

	$("#keepWarmP2").click(function(){
		if($(this).is(':checked')){
			document.getElementById("shutdownP2").disabled = true;
		} else {
			document.getElementById("shutdownP2").disabled = false;
		}
	});

	$("#shutdownTimer").click(function(){
		if($(this).is(':checked')){
			document.getElementById("keepWarmTimer").disabled = true;
		} else {
			document.getElementById("keepWarmTimer").disabled = false;
		}
	});

	$("#keepWarmTimer").click(function(){
		if($(this).is(':checked')){
			document.getElementById("shutdownTimer").disabled = true;
		} else {
			document.getElementById("shutdownTimer").disabled = false;
		}
	});

}); // End of Document Ready Function
