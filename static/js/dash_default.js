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
								(current.notify_data[item].keep_warm != notify_data[item].keep_warm) ) {
								console.log('Notification data change detected.')
								// Update Page
								updateNotificationCard(current.notify_data[item], current.status.mode);
								// Store Notify Data
								notify_data = JSON.parse(JSON.stringify(current.notify_data)); // Copy data to notify_data variable
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
				};

				// Check for a primary_setpoint change
				if ((primary_setpoint != current.current.PSP) && (current.status.mode == 'Hold')) {
					setPrimarySetpointBtn(primary, current.current.PSP);
					primary_setpoint = current.current.PSP;
				};					
			};
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

// Update the notification information for the probe cards
function updateNotificationCard(notify_info, mode) {
	const label = notify_info.label;
	const req = notify_info.req;
	const shutdown = notify_info.shutdown;
	const keep_warm = notify_info.keep_warm;
	const target = notify_info.target;
	console.log('Updating: ' + label + ' Mode: ' + mode);
	// TODO: Update the page item with new data
	const notify_btn_id = label + "_notify_btn";
	if(req) {
		console.log('Turning on this notification: ' + notify_btn_id);
		document.getElementById(notify_btn_id).innerHTML = '<i class="far fa-bell"></i>&nbsp; ' + target + '&deg;' + units;
		document.getElementById(notify_btn_id).className = 'btn btn-sm btn-primary';
	} else {
		console.log('Turning off this notification: ' + notify_btn_id);
		document.getElementById(notify_btn_id).innerHTML = '<i class="far fa-bell-slash"></i>';
		document.getElementById(notify_btn_id).className = 'btn btn-sm btn-outline-primary';
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

// Main
$(document).ready(function(){
	// Setup Listeners 
	$('#reloadPage').click(function() {
		// Reload page when server side changes detected. 
		location.reload(); 
	});

	// Initialize Probe Cards
	initProbeCards();
	
	// Current temperature(s) loop
	probe_loop = setInterval(updateProbeCards, 500); // Update every 500ms 
    
	// Get initial hopper information 
	updateHopperStatus();
	
	// Current hopper information loop
	setInterval(updateHopperStatus, 150000);  // Update every 150000ms 
});
