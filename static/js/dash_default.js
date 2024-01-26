// Dashboard Default JS

// Global Variables 
var hopper_level = 100;
var hopper_pellets = '';
var ui_hash = '';
var primary_setpoint = -1;
var mode = '';
var probe_loop; // variable for the interval function
var notify_data = []; // store all notify data
var probes = []; // List of probe keys 
var primary = ''; // Primary key 
var probeGauges = {}; // List of probe gauges 
var probesReady = false; // Pre-initialized state
// Set max temperatures for units specified 
if (units == 'F') {
	var maxTempPrimary = 600; 
	var maxTempFood = 300;
} else {
	var maxTempPrimary = 300; 
	var maxTempFood = 150;
}
var last_fan_status = null;
var last_auger_status = null;
var last_igniter_status = null;
var last_pmode_status = null;
var last_lid_open_status = false;
var display_mode = null;
var dashDataStruct = {};

// Credits to https://github.com/naikus for SVG-Gauge (https://github.com/naikus/svg-gauge) MIT License Copyright (c) 2016 Aniket Naik
var Gauge = window.Gauge;

function initProbeCards() {
	req = $.ajax({
		url : '/api/current',
		type : 'GET',
		success : function(current){
			// Update current probe temperatures an store probe labels
			for (key in current.current.P) {
				probes.push(key);  // Store probe name to use with notify data
				primary = key;
				probeGauges[key] = initProbeGauge(key);
				probeGauges[key].setValue(0);
			};
			for (key in current.current.F) {
				probes.push(key);  // Store probe name to use with notify data 
				probeGauges[key] = initProbeGauge(key);
				probeGauges[key].setValue(0);
			};
			probesReady = true;
		}
	});
};

function initProbeGauge(key) {
	// Create a new Gauge
	if (key == primary) {
		var maxTemp = maxTempPrimary;
	} else {
		var maxTemp = maxTempFood;
	};
	var probeGauge = Gauge(document.getElementById(key+"_gauge"), {
		max: maxTemp,
		// custom label renderer
		label: function(value) {
		return Math.round(value);
		},
		value: 0,
		// Custom dial colors (Optional)
		color: function(value) {
			if(value <= maxTemp) {
				return "#3498db"; // default color
			}else {
				return "#ef4655"; // if exceeds max value, RED 
			};
		}
	});

	return probeGauge;
};

// Update temperatures on probe status cards
function updateProbeCards() {
	req = $.ajax({
		url : '/api/current',
		type : 'GET',
		success : function(current){
			// Local Variables:
			
			// Check for server side changes and reload if needed
			if (ui_hash == '') {
				ui_hash = current.status.ui_hash;
			} else if ((current.status.ui_hash != ui_hash)) {
				console.log('Detected UI Hash Change.');
				$("#serverReloadModal").modal('show');
				clearInterval(probe_loop);  // Stop getting current data from the server
			};

			if (probesReady) {
				// Update current probe temperatures an store probe labels
				for (key in current.current.P) {
					updateTempCard(key, current.current.P[key]);
				};
				for (key in current.current.F) {
					updateTempCard(key, current.current.F[key]);
				};

				// Check for an update to notifications data 
				if (notify_data.length == 0) {
					console.log('Initializing notify_data.')
					notify_data = JSON.parse(JSON.stringify(current.notify_data)); // Copy data to notify_data variable
					initTargets();
				} else {
					//console.log(probes);
					for(item in current.notify_data) {
						if (probes.includes(current.notify_data[item].label)) {
							//console.log('Found! ' + current.notify_data[item].label);
							//console.log('Data: ' + notify_data[item].label);
							//console.log('current: ' + current.notify_data[item].target + ' last: ' + notify_data[item].target);
							if ((current.notify_data[item].target != notify_data[item].target) || 
								(current.notify_data[item].req != notify_data[item].req) ||
								(current.notify_data[item].shutdown != notify_data[item].shutdown) ||
								(current.notify_data[item].keep_warm != notify_data[item].keep_warm) || 
								(current.notify_data[item].eta != notify_data[item].eta)
								) {
								console.log('Notification data change detected.')
								// Update Page
								updateNotificationCard(current.notify_data[item], current.status.mode);
								// Store Notify Data
								notify_data[item] = JSON.parse(JSON.stringify(current.notify_data[item])); // Copy data to notify_data variable
							};
						};
					};
				};

				// Check for mode change
				if (mode != current.status.mode) {
					if (current.status.mode == 'Hold') {
						setPrimarySetpointBtn(primary, current.current.PSP);
						primary_setpoint = current.current.PSP;
					} else {
						clearPrimarySetpointBtn(primary);
					};
					mode = current.status.mode;
					if (['Prime', 'Shutdown'].includes(mode)) {
						$('#status_footer').slideDown();
						$('#mode_timer_label').show();
						$('#lid_open_label').hide();
						$('#pmode_group').hide();
					} else if (['Startup', 'Reignite'].includes(mode)) {
						$('#status_footer').slideDown();
						$('#mode_timer_label').show();
						$('#lid_open_label').hide();
						$('#pmode_group').show();
					} else if (mode == 'Hold') {
						$('#status_footer').slideUp();
						$('#mode_timer_label').hide();
						$('#lid_open_label').show();
						$('#pmode_group').hide();
					} else if (mode == 'Smoke') {
						$('#status_footer').slideUp();
						$('#mode_timer_label').hide();
						$('#lid_open_label').hide();
						$('#pmode_group').show();
					} else {
						$('#status_footer').slideUp();
						$('#mode_timer_label').hide();
						$('#lid_open_label').hide();
						$('#pmode_group').hide();
					};
					$('#mode_status').html('<b>' + mode +'</b>');
				};

				if ((current.status.mode == 'Recipe') && (display_mode != current.status.display_mode)) {
					display_mode = current.status.display_mode;
					$('#mode_status').html('<b>Recipe | ' + display_mode +'</b>');
				};

				// Check for a primary_setpoint change
				if ((primary_setpoint != current.current.PSP) && (current.status.mode == 'Hold')) {
					setPrimarySetpointBtn(primary, current.current.PSP);
					primary_setpoint = current.current.PSP;
				};					
			};

			if (current.status.outpins.fan != last_fan_status) {
				last_fan_status = current.status.outpins.fan;
				if (last_fan_status) {
					document.getElementById('fan_status').innerHTML = '<i class="fas fa-fan fa-spin fa-2x" data-toggle="tooltip" data-placement="top" title="Fan ON" style="color:rgb(50, 122, 255)"></i>';
				} else {
					document.getElementById('fan_status').innerHTML = '<i class="fas fa-fan fa-2x" data-toggle="tooltip" data-placement="top" title="Fan OFF" style="color:rgb(150, 150, 150)"></i>';
				};
			};

			if (current.status.outpins.auger != last_auger_status) {
				last_auger_status = current.status.outpins.auger;
				if (last_auger_status) {
					document.getElementById('auger_status').innerHTML = '<i class="fas fa-angle-double-right fa-beat fa-2x" data-toggle="tooltip" data-placement="top" title="Auger ON" style="color:rgb(132, 206, 22)"></i>';
				} else {
					document.getElementById('auger_status').innerHTML = '<i class="fas fa-angle-double-right fa-2x" data-toggle="tooltip" data-placement="top" title="Auger OFF" style="color:rgb(150, 150, 150)"></i>';
				};
			}; 

			if (current.status.outpins.igniter != last_igniter_status) {
				last_igniter_status = current.status.outpins.igniter;
				if (last_igniter_status) {

					document.getElementById('igniter_status').innerHTML = '<i class="fas fa-fire fa-beat-fade fa-2x" data-toggle="tooltip" data-placement="top" title="Igniter ON" style="color:rgb(235, 212, 0)"></i>';
				} else {
					document.getElementById('igniter_status').innerHTML = '<i class="fas fa-fire fa-2x" data-toggle="tooltip" data-placement="top" title="Igniter OFF" style="color:rgb(150, 150, 150)"></i>';
				};
			};

			if (current.status.p_mode != last_pmode_status) {
				last_pmode_status = current.status.p_mode;
				if (last_pmode_status == 0) {
					document.getElementById('pmode_status').innerHTML = '<i class="far fa-square fa-stack-2x" style="color:rgb(150, 150, 150)" data-toggle="tooltip" data-placement="top" title="P-Mode"></i><i class="fas fa-minus fa-stack-1x" style="color:rgb(150, 150, 150)"></i>';
					document.getElementById('pmode_btn').innerHTML = '<i class="fa-solid fa-p"></i>-<i class="fas fa-' + last_pmode_status + '"></i>';
				} else if (last_pmode_status < 10) {
					document.getElementById('pmode_status').innerHTML = '<i class="far fa-square fa-stack-2x" style="color:rgb(175, 0, 175)" data-toggle="tooltip" data-placement="top" title="P-Mode"></i><i class="fas fa-' + last_pmode_status + ' fa-stack-1x" style="color:rgb(175, 0, 175)"></i>';
					document.getElementById('pmode_btn').innerHTML = '<i class="fa-solid fa-p"></i>-<i class="fas fa-' + last_pmode_status + '"></i>';
				};
			};

			// Update Timers 
			if (['Prime', 'Startup', 'Reignite', 'Shutdown'].includes(mode)) {
				var duration = 0;
				// Calculate time remaining
				if (['Startup', 'Reignite'].includes(mode)) {
					duration = current.status.start_duration;
				} else if (mode == 'Prime') {
					duration = current.status.prime_duration;
				} else {
					duration = current.status.shutdown_duration;
				};
				var now = new Date().getTime();
				now = Math.floor(now / 1000)
				var start_time = Math.floor(current.status.start_time);  
				var countdown = Math.floor(duration - (now - start_time));
				// Update #mode_timer if > 0, else 0 
				if (countdown < 0) {
					countdown = 0;
				};
				$('#mode_timer').html(countdown);
			};

			// Check Lid Status 
			if ((mode == 'Hold') && (last_lid_open_status != current.status.lid_open_detected)) {
				last_lid_open_status = current.status.lid_open_detected;
				if (last_lid_open_status) {
					$('#status_footer').slideDown();
					$('#mode_timer_label').hide();
					$('#lid_open_label').show();
				} else {
					$('#status_footer').slideUp();
					$('#mode_timer_label').hide();
					$('#lid_open_label').show();
				};
			}; 

			if ((mode == 'Hold') && (last_lid_open_status)) {
				// Calculate duration 
				var countdown = 0;
				var now = new Date().getTime();
				now = Math.floor(now / 1000)
				var end_time = Math.floor(current.status.lid_open_endtime);  
				var countdown = Math.floor(end_time - now);
				// Display duration
				if (countdown < 0) {
					countdown = 0;
				};
				$('#lid_open_label').html('Lid Open Detected: PID Paused ' + countdown + 's');
			};
			
			// Update Elapsed Time 
			if (current.status.startup_timestamp != 0) {
				var time_now = new Date().getTime();
				time_now = Math.floor(time_now / 1000);
				//console.log('Time Now Adjusted: ' + time_now);
				var time_elapsed = time_now - Math.floor(current.status.startup_timestamp);
				var time_elapsed_string = formatDuration(time_elapsed);
				$('#time_elapsed_string').html(time_elapsed_string);
				document.getElementById('time_elapsed_string').className = 'text-primary';
			} else {
				$('#time_elapsed_string').html('--');
				document.getElementById('time_elapsed_string').className = 'text-secondary';
			};

			//if (current.status.s_plus) {
			//	document.getElementById('smokeplus_status').innerHTML = '<i class="fas fa-cloud fa-stack-2x" style="color:rgb(104, 0, 104)" data-toggle="tooltip" data-placement="top" title="Smoke Plus ON"></i><i class="fas fa-plus fa-stack-1x fa-inverse"></i>';
			//} else {
			//	document.getElementById('smokeplus_status').innerHTML = '<i class="fas fa-cloud fa-stack-2x" style="color:rgb(150, 150, 150)" data-toggle="tooltip" data-placement="top" title="Smoke Plus OFF"></i><i class="fas fa-plus fa-stack-1x fa-inverse"></i>';
			//};

		}
	});
};

// Update the temperature for a specific probe/card 
function updateTempCard(key, temp) {
	probeGauges[key].setValueAnimated(temp, 0.25); // (value, animation duration in seconds)
};

// Initialize the notification target sliders for the notification modal
function initTargets() {
	for (item in notify_data) {
		if (notify_data[item].type == 'probe') {
			outputTargetId = notify_data[item].label + '_tempOutputId';
			inputTargetId = '#' + notify_data[item].label + '_tempInputId';
			targetValue = notify_data[item].target;
			document.getElementById(outputTargetId).innerHTML = targetValue;
			$(inputTargetId).val(targetValue);
		};
	};
};

function formatDuration(total_seconds) {
	const hours = Math.floor(total_seconds / 3600);
	const minutes = Math.floor((total_seconds % 3600) / 60);
	const seconds = total_seconds % 60;
  
	if (hours) {
	  return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
	} else if (minutes) {
	  return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
	} else {
	  return `${seconds.toString().padStart(2, '0')}s`;
	}
};

// Update the notification information for the probe cards
function updateNotificationCard(notify_info, mode) {
	const label = notify_info.label;
	const req = notify_info.req;
	const shutdown = notify_info.shutdown;
	const keep_warm = notify_info.keep_warm;
	const target = notify_info.target;
	var eta = '<i class="fa-solid fa-spinner fa-spin-pulse"></i>';
	if (notify_info.eta != null) {
		eta = formatDuration(notify_info.eta);
	};
	console.log('Updating: ' + label + '  ETA: ' + eta);
	// TODO: Update the page item with new data
	const notify_btn_id = label + "_notify_btn";
	const eta_btn_id = label + "_eta_btn";

	if(req) {
		console.log('Updating this notification: ' + notify_btn_id);
		document.getElementById(notify_btn_id).innerHTML = '<i class="far fa-bell"></i>&nbsp; ' + target + '&deg;' + units; 
		document.getElementById(eta_btn_id).innerHTML = '<i class="fa-solid fa-hourglass-half"></i>&nbsp; ' + eta;
		document.getElementById(notify_btn_id).className = 'btn btn-sm btn-primary';
		$('#'+eta_btn_id).show();
	} else {
		console.log('Turning off this notification: ' + notify_btn_id);
		document.getElementById(notify_btn_id).innerHTML = '<i class="far fa-bell-slash"></i>';
		document.getElementById(notify_btn_id).className = 'btn btn-sm btn-outline-primary';
		$('#'+eta_btn_id).hide();
	};
};

// Set Notification Request and Send to the Server
function setNotify(probe_label, target) {
	// Get checkboxes (shutdown / keep warm)
	var shutdown = false;
	var keepWarm = false;
	if ($("#"+probe_label +"_shutdown").is(':checked')){
		shutdown = true;
	};
	if ($("#"+probe_label +"_keepWarm").is(':checked')){
		keepWarm = true;
	};

	// Send to server
	var updated_notify_data = JSON.parse(JSON.stringify(notify_data)); // Copy notify_data into a new variable

	for (item in updated_notify_data) {
		if (updated_notify_data[item].label == probe_label) {
			updated_notify_data[item].target = parseInt(target);
			updated_notify_data[item].shutdown = shutdown;
			updated_notify_data[item].keep_warm = keepWarm;
			updated_notify_data[item].req = true;
		};
	};

    var postdata = { 
        'notify_data' : updated_notify_data
    };

	$.ajax({
        url : '/api/control',
        type : 'POST',
        data : JSON.stringify(postdata),
        contentType: "application/json; charset=utf-8",
        traditional: true,
        success: function (data) {
            console.log('Notification Settings Sent: ' + data.control);
        }
    });
};

// Cancel Notification Request
function cancelNotify(probe_label) {
	// Send to server
	var updated_notify_data = JSON.parse(JSON.stringify(notify_data)); // Copy notify_data into a new variable

	for (item in updated_notify_data) {
		if (updated_notify_data[item].label == probe_label) {
			updated_notify_data[item].req = false;  // Set request to false
			updated_notify_data[item].shutdown = false;  // Set shutdown to false
			updated_notify_data[item].keep_warm = false;  // Set keep_warm to false
			updated_notify_data[item].target = 0;  // Set target to 0
		};
	};

    var postdata = { 
        'notify_data' : updated_notify_data
    };

	$.ajax({
        url : '/api/control',
        type : 'POST',
        data : JSON.stringify(postdata),
        contentType: "application/json; charset=utf-8",
        traditional: true,
        success: function (data) {
            console.log('Notification Cancel Sent: ' + data.control);
        }
    });

};

// Update the target temperature for primary probe
function setPrimarySetpointBtn(primary_label, target) {
	console.log('Updating the Primary Setpoint: ' + target);
	primary_btn_id = primary_label + '_primary_setpoint_btn';
	document.getElementById(primary_btn_id).innerHTML = '<i class="fas fa-crosshairs"></i>&nbsp; ' + target + '&deg;' + units;
	document.getElementById(primary_btn_id).className = 'btn btn-sm btn-primary';
	$("#"+primary_btn_id).show();
};

// Hide the target icon for primary probe
function clearPrimarySetpointBtn(primary_label) {
	console.log('Concealing Target Icon');
	primary_btn_id = primary_label + '_primary_setpoint_btn';
	$("#"+primary_btn_id).hide();
};

// Update the hopper status
function updateHopperStatus() {
	req = $.ajax({
		url : '/api/hopper',
		type : 'GET',
		success : function(hopper){
			// Update Hopper Level
			hopper_level = hopper.hopper_level

			if (hopper_level > 69) {
				document.getElementById("hopperLevel").className = "progress-bar progress-bar-striped bg-success";
			} else if (hopper_level > 29) {
				document.getElementById("hopperLevel").className = "progress-bar progress-bar-striped bg-warning";
			} else {
				document.getElementById("hopperLevel").className = "progress-bar progress-bar-striped bg-danger";
			};

			document.getElementById("hopperLevel").style.width = hopper_level + "%";
			document.getElementById("hopperLevel").innerHTML = hopper_level + "%";

			// Update Brand / Wood Pellet Info
			hopper_pellets = hopper.hopper_pellets
			document.getElementById("hopperPellets").innerHTML = hopper_pellets;

			//console.log(hopper); // Debug Print 
		}
	});
};

function refreshHopperStatus() {
    var postdata = { 
        'hopper_check' : true
    };

	$.ajax({
        url : '/api/control',
        type : 'POST',
        data : JSON.stringify(postdata),
        contentType: "application/json; charset=utf-8",
        traditional: true,
        success: function (data) {
            console.log('Refresh Hopper Level/Status: ' + data.control);
			const hopper_check = setInterval(function(){
				updateHopperStatus();
				clearInterval(hopper_check);
			}, 500);
        }
    });
};

// Launch the setpointModal from the notification toolbar
function launchSetpointModal() {
	$("#setpointModal").modal('show');
};

function setPmode(pmode) {
    var postdata = { 
        'cycle_data' : {
			'PMode' : pmode
		}
    };

	$.ajax({
        url : '/api/settings',
        type : 'POST',
        data : JSON.stringify(postdata),
        contentType: "application/json; charset=utf-8",
        traditional: true,
        success: function (data) {
			var postdata = { 
				'settings_update' : true
			};

			$.ajax({
				url : '/api/control',
				type : 'POST',
				data : JSON.stringify(postdata),
				contentType: "application/json; charset=utf-8",
				traditional: true,
				success: function (data) {
				}
			});
        }
    });
};

// Show the Dashboard Settings Modal/Dialog when clicked
function dashSettings() {
	$("#dashSettingsModal").modal('show');
	//dashData();
};

// Get dashboard data structure
function dashGetData() {
	req = $.ajax({
		url : '/api/settings',
		type : 'GET',
		success : function(settings){
			dashDataStruct = settings.settings.dashboard.dashboards.Default;
			//console.log('dashData Hidden='+dashDataStruct.custom.hidden_cards);
			//console.log('dashData Name='+dashDataStruct.name);
		}
	});
};

// Set dashboard data structure
function dashSetData() {
	var postdata = { 
		'dashboard' : {
			'dashboards' : {
				'Default' : dashDataStruct
			}
		} 
    };

	$.ajax({
        url : '/api/settings',
        type : 'POST',
        data : JSON.stringify(postdata),
        contentType: "application/json; charset=utf-8",
        traditional: true,
        success: function (response) {
            //console.log('dashSetData -> ' + response);
        }
    });
};

function dashToggleVisible(cardID) {
	if ($('#card_'+cardID).is(":hidden")) {
		// change card to visible
		$('#card_'+cardID).show();
		// update dash config icon
		$('#visibleStatus_'+cardID).html('<i class="fa-solid fa-eye text-success"></i>&nbsp;');
		// save to settings
		var index = dashDataStruct.custom.hidden_cards.indexOf(cardID); // Index of cardID
		if (index !== -1) {
			dashDataStruct.custom.hidden_cards.splice(index, 1); // If found, remove
		};
		//console.log('dashData Hidden='+dashDataStruct.custom.hidden_cards);
		dashSetData();
	} else {
		// change card to hidden
		$('#card_'+cardID).hide();
		// update dash config icon
		$('#visibleStatus_'+cardID).html('<i class="fa-solid fa-eye-slash text-secondary"></i>&nbsp;');
		// save to settings
		var index = dashDataStruct.custom.hidden_cards.indexOf(cardID); // Index of cardID
		if (index == -1) {
			dashDataStruct.custom.hidden_cards.push(cardID); // If not found, add
		};
		//console.log('dashData Hidden='+dashDataStruct.custom.hidden_cards);
		dashSetData();
	};
}

// Main
$(document).ready(function(){
	// Setup Listeners 
	$('#reloadPage').click(function() {
		// Reload page when server side changes detected. 
		location.reload(); 
	});

	// Initialize Dashboard Data
	dashGetData();

	// Initialize Probe Cards
	initProbeCards();
	
	// Current temperature(s) loop
	probe_loop = setInterval(updateProbeCards, 500); // Update every 500ms 
    
	// Get initial hopper information 
	updateHopperStatus();
	
	// Current hopper information loop
	setInterval(updateHopperStatus, 150000);  // Update every 150000ms 
});
