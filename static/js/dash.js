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

        // console.log(data);

        // Setup Dash Circles 

        var GrillTempCircle = circliful.newCircle({
            percent: ((data.cur_probe_temps[0] * 100) / 600),
            id: 'GrillTempCircle',
            type: 'simple',
            foregroundCircleWidth: 10,
            startAngle: -180,
            backgroundCircleWidth: 10,
            text: data.cur_probe_temps[0] + '°F',
            textReplacesPercentage: true,
                strokeLinecap: "round",
        });
        
        var probe1_temp = 0;
        var probe1_text = 'OFF';
        var probe2_temp = 0;
        var probe2_text = 'OFF';

        if(data.probes_enabled[1] == 1) {
            probe1_temp = data.cur_probe_temps[1];
            probe1_text = probe1_temp + '°F';
        };

        if(data.probes_enabled[2] == 1) {
            probe2_temp = data.cur_probe_temps[2];
            probe2_text = probe2_temp + '°F';
        };

        var Probe1TempCircle = circliful.newCircle({
            percent: ((probe1_temp * 100) / 300),
            id: 'Probe1TempCircle',
            type: 'simple',
            foregroundCircleWidth: 10,
            startAngle: -180,
            backgroundCircleWidth: 10,
            text: probe1_text,
            textReplacesPercentage: true,
                strokeLinecap: "round",
        });
        
        var Probe2TempCircle = circliful.newCircle({
            percent: ((probe2_temp * 100) / 300),
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
            $("#smoke_inactive_btn").hide();
            $("#hold_inactive_btn").hide();
        } else if (data.current_mode == 'Monitor') {
            document.getElementById("monitor_btn").className = "btn btn-secondary border border-secondary";
            $("#active_group").hide();
            $("#smoke_inactive_btn").hide();
            $("#hold_inactive_btn").hide();
        } else if ((data.current_mode == 'Startup') || (data.current_mode == 'Reignite')) {
            document.getElementById("startup_btn").className = "btn btn-success border border-secondary";
            $("#active_group").hide();
            $("#monitor_btn").hide();
        } else if (data.current_mode == 'Smoke') {
            document.getElementById("smoke_btn").className = "btn btn-warning border border-secondary";
            $("#inactive_group").hide();
            $("#stop_btn").hide();
        } else if (data.current_mode == 'Hold') {
            document.getElementById("hold_btn").className = "btn btn-secondary border border-secondary text-white";
            document.getElementById("hold_btn").innerHTML = data.set_points['grill'] + "°F";
            $("#inactive_group").hide();
            $("#stop_btn").hide();
        } else if (data.current_mode == 'Shutdown') {
            document.getElementById("shutdown_btn").className = "btn btn-danger border border-secondary";
            $("#inactive_group").hide();
        };

        if ((data.current_mode == 'Smoke') || (data.current_mode == 'Hold')) {
            if(data.splus == true) {
                document.getElementById("splus_btn").className = "btn btn-success border border-secondary";
                document.getElementById("splus_btn").value = "false";
            } else {
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
                GrillTempCircle.update([
                    { type: "percent", value: ((data.cur_probe_temps[0] * 100) / 600) },
                    { type: "text", value: data.cur_probe_temps[0] + "°F" }
                ]);
    
                if(data.probes_enabled[1] == 1) {
                    Probe1TempCircle.update([
                        { type: "percent", value: ((data.cur_probe_temps[1] * 100) / 300) },
                        { type: "text", value: data.cur_probe_temps[1] + "°F" }
                    ]);
                } else {
                    Probe1TempCircle.update([
                        { type: "percent", value: 0 },
                        { type: "text", value: "OFF" }
                    ]);
                };
    
                if(data.probes_enabled[2] == 1) {
                    Probe2TempCircle.update([
                        { type: "percent", value: ((data.cur_probe_temps[2] * 100) / 300) },
                        { type: "text", value: data.cur_probe_temps[2] + "°F" }
                    ]);
                } else {
                    Probe2TempCircle.update([
                        { type: "percent", value: 0 },
                        { type: "text", value: "OFF" }
                    ]);
                };
    
                // Update Buttons

                // If mode changed
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
                    } else if (data.current_mode == 'Monitor') {
                        document.getElementById("monitor_btn").className = "btn btn-secondary border border-secondary";
                        $("#active_group").hide();
                        $("#splus_btn").hide();
                        $("#inactive_group").show();
                        $("#smoke_inactive_btn").hide();
                        $("#hold_inactive_btn").hide();
                    } else if ((data.current_mode == 'Startup') || (data.current_mode == 'Reignite')) {
                        document.getElementById("startup_btn").className = "btn btn-success border border-secondary";
                        $("#active_group").hide();
                        $("#splus_btn").hide();
                        $("#inactive_group").show();
                        $("#smoke_inactive_btn").show();
                        $("#hold_inactive_btn").show();
                        $("#monitor_btn").hide();
                    } else if (data.current_mode == 'Smoke') {
                        document.getElementById("smoke_btn").className = "btn btn-warning border border-secondary";
                        $("#inactive_group").hide();
                        $("#active_group").show();
                        $("#stop_btn").hide();
                        $("#splus_btn").show();
                    } else if (data.current_mode == 'Hold') {
                        $("#inactive_group").hide();
                        $("#active_group").show();
                        $("#splus_btn").show();
                        document.getElementById("hold_btn").className = "btn btn-secondary border border-secondary text-white";
                        document.getElementById("hold_btn").innerHTML = data.set_points['grill'] + "°F";
                        $("#stop_btn").hide();
                    } else if (data.current_mode == 'Shutdown') {
                        $("#inactive_group").hide();
                        $("#splus_btn").hide();
                        $("#active_group").show();
                        $("#stop_btn").show();
                        document.getElementById("shutdown_btn").className = "btn btn-danger border border-secondary";
                    };
            
                }
                if ((data.current_mode == 'Smoke') || (data.current_mode == 'Hold')) {
                    if (last_splus != data.splus) {
                        if(data.splus == true) {
                            document.getElementById("splus_btn").className = "btn btn-success border border-secondary";
                            document.getElementById("splus_btn").value = "false";
                        } else {
                            document.getElementById("splus_btn").className = "btn btn-outline-primary border border-secondary text-secondary";
                            document.getElementById("splus_btn").value = "true";
                        };
                        last_splus = data.splus;
                    };
                };
            });
        }, 2000);
        
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
