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

        // console.log(data);

        // Setup Dash Circles 
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

        var GrillTempCircle = circliful.newCircle({
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
        
        var notify_req_last = {};
        notify_req_last['grill'] = data.notify_req['grill']; 
        notify_req_last['probe1'] = data.notify_req['probe1'];
        notify_req_last['probe2'] = data.notify_req['probe2'];

        if(data.notify_req['grill']) { 
            // If notify request is active, change the button highlighting
            document.getElementById("grill_notify_btn").className = "btn btn-primary";
            // Change the text to indicate setpoint
            document.getElementById("grill_notify_btn").innerHTML = "<i class=\"fas fa-bell\"></i> " + data.set_points['grill'] + "°" + units;
        } else {
            // If notify request is not active, change the button highlighting
            document.getElementById("grill_notify_btn").className = "btn btn-outline-primary";
            // Change the text to show bell with slash
            document.getElementById("grill_notify_btn").innerHTML = "<i class=\"far fa-bell-slash\"></i>";
        };

        var probe1_temp = 0;
        var probe1_text = 'OFF';
        var probe2_temp = 0;
        var probe2_text = 'OFF';

        if(data.probes_enabled[1] == 1) {
            probe1_temp = data.cur_probe_temps[1];
            probe1_text = probe1_temp + "°" + units;
            if(data.notify_req['probe1']) { 
                // If notify request is active, change the button highlighting
                document.getElementById("probe1_notify_btn").className = "btn btn-primary";
                // Change the text to indicate setpoint
                document.getElementById("probe1_notify_btn").innerHTML = "<i class=\"fas fa-bell\"></i> " + data.set_points['probe1'] + "°" + units;
            } else {
                // If notify request is not active, change the button highlighting
                document.getElementById("probe1_notify_btn").className = "btn btn-outline-primary";
                // Change the text to show bell with slash
                document.getElementById("probe1_notify_btn").innerHTML = "<i class=\"far fa-bell-slash\"></i>";
            };
        };

        if(data.probes_enabled[2] == 1) {
            probe2_temp = data.cur_probe_temps[2];
            probe2_text = probe2_temp + "°" + units;
            if(data.notify_req['probe2']) { 
                // If notify request is active, change the button highlighting
                document.getElementById("probe2_notify_btn").className = "btn btn-primary";
                // Change the text to indicate setpoint
                document.getElementById("probe2_notify_btn").innerHTML = "<i class=\"fas fa-bell\"></i> " + data.set_points['probe2'] + "°" + units;
            } else {
                // If notify request is not active, change the button highlighting
                document.getElementById("probe2_notify_btn").className = "btn btn-outline-primary";
                // Change the text to show bell with slash
                document.getElementById("probe2_notify_btn").innerHTML = "<i class=\"far fa-bell-slash\"></i>";
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

        var Probe1TempCircle = circliful.newCircle({
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

        var Probe2TempCircle = circliful.newCircle({
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

        // Setup Dash Buttons

        var last_mode = data.current_mode;
        var last_splus = data.splus;

        if (data.current_mode == "Stop") {
            document.getElementById("stop_inactive_btn").className = "btn btn-danger border border-secondary";
            $("#active_group").hide();
            $("#inactive_group").show();
            $("#smoke_inactive_btn").hide();
            $("#hold_inactive_btn").hide();
            $("#error_btn").hide();
        } else if (data.current_mode == 'Monitor') {
            document.getElementById("monitor_btn").className = "btn btn-secondary border border-secondary";
            $("#active_group").hide();
            $("#inactive_group").show();
            $("#smoke_inactive_btn").hide();
            $("#hold_inactive_btn").hide();
            $("#error_btn").hide();
        } else if ((data.current_mode == 'Startup') || (data.current_mode == 'Reignite')) {
            document.getElementById("startup_btn").className = "btn btn-success border border-secondary";
            $("#active_group").hide();
            $("#inactive_group").show();
            $("#monitor_btn").hide();
            $("#error_btn").hide();
        } else if (data.current_mode == 'Smoke') {
            document.getElementById("smoke_btn").className = "btn btn-warning border border-secondary";
            $("#inactive_group").hide();
            $("#active_group").show();
            $("#stop_btn").hide();
            $("#error_btn").hide();
        } else if (data.current_mode == 'Hold') {
            document.getElementById("hold_btn").className = "btn btn-secondary border border-secondary text-white";
            document.getElementById("hold_btn").innerHTML = data.set_points['grill'] + "°" + units;
            $("#inactive_group").hide();
            $("#active_group").show();
            $("#stop_btn").hide();
            $("#error_btn").hide();
        } else if (data.current_mode == 'Shutdown') {
            document.getElementById("shutdown_btn").className = "btn btn-danger border border-secondary";
            $("#inactive_group").hide();
            $("#active_group").show();
            $("#error_btn").hide();
        } else if (data.current_mode == 'Error') {
            document.getElementById("stop_inactive_btn").className = "btn btn-danger border border-secondary";
            $("#active_group").hide();
			$("#smoke_inactive_btn").hide();
            $("#hold_inactive_btn").hide();
            $("#inactive_group").show();
			$("#error_btn").show();
			document.getElementById("error_btn").className = "btn btn-danger border border-secondary";
		};

        if ((data.current_mode == 'Smoke') || (data.current_mode == 'Hold')) {
            if(data.splus == true) {
                $("#splus_btn").show();
                document.getElementById("splus_btn").className = "btn btn-success border border-secondary";
                document.getElementById("splus_btn").value = "false";
            } else {
                $("#splus_btn").show();
                document.getElementById("splus_btn").className = "btn btn-outline-primary border border-secondary text-secondary";
                document.getElementById("splus_btn").value = "true";
            };
        } else {
            $("#splus_btn").hide();
        };

        setInterval(function(){
            // Get Dash Data
            req = $.ajax({
                url : '/dashdata',
                type : 'GET'
            });
    
            req.done(function(data) {
                // Update Dash Data
                //console.log(data);

                //console.log("Last Mode = " + last_mode);
    
                // Update Circles

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

				GrillTempCircle.update([
                    { type: "percent", value: grillPercent },
                    { type: "text", value: data.cur_probe_temps[0] + "°" + units }
                ]);
    
                if(data.probes_enabled[1] == 1) {
					if(data.cur_probe_temps[1] < 0) {
						// if negative temperature, then don't display circle temp bar
						var probe1Percent = 0;
					} else if(units == 'F'){
						// if units are F, adjust circle temp bar where max is 300F
						var probe1Percent = ((data.cur_probe_temps[1] * 100) / 300);
					} else {
						// if units are C, adjust circle temp bar where max is 150C
						var probe1Percent = ((data.cur_probe_temps[1] * 100) / 150);
					};
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
    
                if(data.probes_enabled[2] == 1) {
					if(data.cur_probe_temps[2] < 0) {
						// if negative temperature, then don't display circle temp bar
						var probe2Percent = 0;
					} else if(units == 'F'){
						// if units are F, adjust circle temp bar where max is 300F
						var probe2Percent = ((data.cur_probe_temps[2] * 100) / 300);
					} else {
						// if units are C, adjust circle temp bar where max is 150C
						var probe2Percent = ((data.cur_probe_temps[2] * 100) / 150);
					};
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
    
                // Update notify buttons if state changes

                if(notify_req_last['grill'] != data.notify_req['grill']) { 
                    notify_req_last['grill'] = data.notify_req['grill']; 
                    if(data.notify_req['grill']) { 
                        // If notify request is active, change the button highlighting
                        document.getElementById("grill_notify_btn").className = "btn btn-primary";
                        // Change the text to indicate setpoint
                        document.getElementById("grill_notify_btn").innerHTML = "<i class=\"fas fa-bell\"></i> " + data.set_points['grill'] + "°" + units;
                    } else {
                        // If notify request is not active, change the button highlighting
                        document.getElementById("grill_notify_btn").className = "btn btn-outline-primary";
                        // Change the text to show bell with slash
                        document.getElementById("grill_notify_btn").innerHTML = "<i class=\"far fa-bell-slash\"></i>";
                    };
                };

                if(notify_req_last['probe1'] != data.notify_req['probe1']) { 
                    notify_req_last['probe1'] = data.notify_req['probe1']; 
                    if(data.notify_req['probe1']) { 
                        // If notify request is active, change the button highlighting
                        document.getElementById("probe1_notify_btn").className = "btn btn-primary";
                        // Change the text to indicate setpoint
                        document.getElementById("probe1_notify_btn").innerHTML = "<i class=\"fas fa-bell\"></i> " + data.set_points['probe1'] + "°" + units;
                    } else {
                        // If notify request is not active, change the button highlighting
                        document.getElementById("probe1_notify_btn").className = "btn btn-outline-primary";
                        // Change the text to show bell with slash
                        document.getElementById("probe1_notify_btn").innerHTML = "<i class=\"far fa-bell-slash\"></i>";
                    };
                };

                if(notify_req_last['probe2'] != data.notify_req['probe2']) { 
                    notify_req_last['probe2'] = data.notify_req['probe2']; 
                    if(data.notify_req['probe2']) { 
                        // If notify request is active, change the button highlighting
                        document.getElementById("probe2_notify_btn").className = "btn btn-primary";
                        // Change the text to indicate setpoint
                        document.getElementById("probe2_notify_btn").innerHTML = "<i class=\"fas fa-bell\"></i> " + data.set_points['probe2'] + "°" + units;
                    } else {
                        // If notify request is not active, change the button highlighting
                        document.getElementById("probe2_notify_btn").className = "btn btn-outline-primary";
                        // Change the text to show bell with slash
                        document.getElementById("probe2_notify_btn").innerHTML = "<i class=\"far fa-bell-slash\"></i>";
                    };
                };
    

                // Update dock buttons if mode changed
                if(data.current_mode != last_mode) {
                    // Dim relavant button for last_mode
                    if(last_mode == 'Startup') {
                        document.getElementById("startup_btn").className = "btn btn-outline-success border border-secondary";
                    } else if (last_mode == 'Monitor') {
                        document.getElementById("monitor_btn").className = "btn btn-outline-secondary border border-secondary";
                    } else if (last_mode == 'Smoke') {
                        document.getElementById("smoke_btn").className = "btn btn-outline-warning border border-secondary text-secondary";
                    } else if (last_mode == 'Hold') {
                        document.getElementById("hold_btn").className = "btn btn-outline-secondary border border-secondary";
                        document.getElementById("hold_btn").innerHTML = "Hold";
                    } else if (last_mode == 'Shutdown') {
                        document.getElementById("shutdown_btn").className = "btn btn-outline-danger border border-secondary";
                    } else if (last_mode == 'Stop') {
                        document.getElementById("stop_inactive_btn").className = "btn btn-outline-secondary border border-secondary";
                    };
                    // Reset last_mode to current_mode
                    last_mode = data.current_mode;

                    // Update button selection 
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
                            document.getElementById("splus_btn").value = "false";
                        } else {
                            document.getElementById("splus_btn").className = "btn btn-outline-primary border border-secondary text-secondary";
                            document.getElementById("splus_btn").value = "true";
                        };
                        $("#error_btn").hide();
                    } else if (data.current_mode == 'Hold') {
                        $("#inactive_group").hide();
                        $("#active_group").show();
                        $("#splus_btn").show();
                        // This is required when automatically transitioning from another mode to this mode
                        if(data.splus == true) {
                            document.getElementById("splus_btn").className = "btn btn-success border border-secondary";
                            document.getElementById("splus_btn").value = "false";
                        } else {
                            document.getElementById("splus_btn").className = "btn btn-outline-primary border border-secondary text-secondary";
                            document.getElementById("splus_btn").value = "true";
                        };
                        document.getElementById("hold_btn").className = "btn btn-secondary border border-secondary text-white";
                        document.getElementById("hold_btn").innerHTML = data.set_points['grill'] + "°" + units;
                        $("#stop_btn").hide();
                        $("#error_btn").hide();
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
                    };
            
                }
                if ((data.current_mode == 'Smoke') || (data.current_mode == 'Hold')) {
                    if (last_splus != data.splus) {
                        if(data.splus == true) {
                            $("#splus_btn").show();
                            document.getElementById("splus_btn").className = "btn btn-success border border-secondary";
                            document.getElementById("splus_btn").value = "false";
                        } else {
                            $("#splus_btn").show();
                            document.getElementById("splus_btn").className = "btn btn-outline-primary border border-secondary text-secondary";
                            document.getElementById("splus_btn").value = "true";
                        };
                        last_splus = data.splus;
                    };
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
        // console.log(data);  // Debug logging

        // Returned Data: 
        // 'data.hopper_level' 
        if (data.hopper_level > 70) { 
            document.getElementById("HopperStatus").className = "btn btn-outline-success btn-block shadow";
        } else if (data.hopper_level > 30) {
            document.getElementById("HopperStatus").className = "btn btn-outline-warning btn-block shadow";
        } else {
            document.getElementById("HopperStatus").className = "btn btn-outline-danger btn-block shadow";
        };

        document.getElementById("HopperLevel").innerHTML = data.hopper_level;
        document.getElementById("PelletName").innerHTML = data.cur_pellets;
    });

    setInterval(function(){
        // Get Hopper Level every 2.5 minutes
        req = $.ajax({
            url : '/hopperlevel',
            type : 'GET'
        });

        req.done(function(data) {
            // Update Hopper Level
            // console.log(data);  // Debug logging

            // Returned Data: 
            // 'data.hopper_level' 
            if (data.hopper_level > 70) { 
                document.getElementById("HopperStatus").className = "btn btn-outline-success btn-block shadow";
            } else if (data.hopper_level > 30) {
                document.getElementById("HopperStatus").className = "btn btn-outline-warning btn-block shadow";
            } else {
                document.getElementById("HopperStatus").className = "btn btn-outline-danger btn-block shadow";
            };

            document.getElementById("HopperLevel").innerHTML = data.hopper_level;
            document.getElementById("PelletName").innerHTML = data.cur_pellets;
        });
    }, 150000);



}); // End of Document Ready Function
