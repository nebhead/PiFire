// Dashboard JS

// Global Variables 
var errorCounter = 0;
var maxErrorCount = 30;
var hopper_level = 100;
var hopper_pellets = '';
var ui_hash = '';
var primary_setpoint = -1;
var mode = '';
var probe_loop; // variable for the interval function
var notify_data = []; // store all notify data
var notify_status = {}; // store all notify statuses 

var last_fan_status = null;
var last_auger_status = null;
var last_igniter_status = null;
var last_pmode_status = null;
var last_lid_open_status = false;
var display_mode = null;
var dashDataStruct = {};
function initNotifyStatus() {
	// This function creates the notify_status object that indicates the current activated/requested notifications
	for (notify_item in notify_data) {
		if (notify_data[notify_item]['type'] == 'probe') {
			notify_status[notify_data[notify_item]['label']] = {};
			//console.log('Creating notify_status struct for: ' + notify_data[notify_item]['label']);
			if (notify_data[notify_item]['req']) {
				notify_status[notify_data[notify_item]['label']]['probe'] = true;
			} else {
				notify_status[notify_data[notify_item]['label']]['probe'] = false;
			};	
		} else if (notify_data[notify_item]['type'] == 'probe_limit_high') {
			if (notify_data[notify_item]['req']) {
				notify_status[notify_data[notify_item]['label']]['probe_limit_high'] = true;
			} else {
				notify_status[notify_data[notify_item]['label']]['probe_limit_high'] = false;
			};
		} else if (notify_data[notify_item]['type'] == 'probe_limit_low') {
			if (notify_data[notify_item]['req']) {
				notify_status[notify_data[notify_item]['label']]['probe_limit_low'] = true;
			} else {
				notify_status[notify_data[notify_item]['label']]['probe_limit_low'] = false;
			};
		};
	};
};

function initNotifyIndicators(probes) {
	for(item in notify_data) {
		if (probes.includes(notify_data[item].label)) {
			updateNotificationCard(notify_data[item]);
		};
	};
};

// Update temperatures on probe status cards
function updateProbeCards() {
	req = $.ajax({
		url : '/api/current',
		type : 'GET',
		success : function(current){
			// Clear error counter
			if (errorCounter > 0) {
				errorCounter = 0;
				$("#serverOfflineModal").modal('hide');
			};

			// Local Variables:
			var probes = [];
			
			// Check for server side changes and reload if needed
			if (ui_hash == '') {
				ui_hash = current.status.ui_hash;
			} else if ((current.status.ui_hash != ui_hash)) {
				console.log('Detected UI Hash Change.');
				$("#serverReloadModal").modal('show');
				clearInterval(probe_loop);  // Stop getting current data from the server
			};

			// Update current probe temperatures an store probe labels
			for (key in current.current.P) {
				updateTempCard(key, current.current.P[key]);
				probes.push(key);  // Store probe name to use with notify data
				primary = key;
			};
			for (key in current.current.F) {
				updateTempCard(key, current.current.F[key]);
				probes.push(key);  // Store probe name to use with notify data 
			};

			// Check for an update to notifications data 
			if (notify_data.length == 0) {
				console.log('Initializing notify_data.')
				notify_data = JSON.parse(JSON.stringify(current.notify_data)); // Copy data to notify_data variable
				initAllTargets();
				initNotifyStatus();
				initNotifyIndicators(probes);
			} else {
				//console.log(probes);
					// First update notify statuses 
					for(item in current.notify_data) {
						// Update Notify Status
						if (probes.includes(current.notify_data[item].label)) {
							if (current.notify_data[item]['req']) {
								notify_status[current.notify_data[item]['label']][current.notify_data[item]['type']] = true;
								//console.log('Notification Requested: ' + current.notify_data[item]['label'] + ' - ' + current.notify_data[item]['type']);
							} else {
								notify_status[current.notify_data[item]['label']][current.notify_data[item]['type']] = false;
								//console.log('Notification Cancelled: ' + current.notify_data[item]['label'] + ' - ' + current.notify_data[item]['type']);
							};
						};
					};
					// Check for changes in notify data structures 
				for(item in current.notify_data) {
					if (probes.includes(current.notify_data[item].label)) {
						//console.log('Found! ' + current.notify_data[item].label);
						//console.log('Data: ' + notify_data[item].label);
						//console.log('current: ' + current.notify_data[item].target + ' last: ' + notify_data[item].target);
						// Check for changes to triggered state
						var triggered = false;
						if (('triggered' in current.notify_data[item]) && ('triggered' in notify_data[item])) {
							if (current.notify_data[item].triggered != notify_data[item].triggered) {
								var triggered = true;
							};
						};
						if ((current.notify_data[item].target != notify_data[item].target) || 
							(current.notify_data[item].req != notify_data[item].req) ||
							(current.notify_data[item].shutdown != notify_data[item].shutdown) ||
							(current.notify_data[item].keep_warm != notify_data[item].keep_warm) || 
							(current.notify_data[item].eta != notify_data[item].eta) ||
							(triggered)
							) {
							console.log('Notification data change detected.')
							// Store Notify Data
							notify_data[item] = JSON.parse(JSON.stringify(current.notify_data[item])); // Copy data to notify_data variable
								// Update Page
								updateNotificationCard(notify_data[item]);
								initTarget(notify_data[item]);
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
			
			//if (current.status.s_plus) {
			//	document.getElementById('smokeplus_status').innerHTML = '<i class="fas fa-cloud fa-stack-2x" style="color:rgb(104, 0, 104)" data-toggle="tooltip" data-placement="top" title="Smoke Plus ON"></i><i class="fas fa-plus fa-stack-1x fa-inverse"></i>';
			//} else {
			//	document.getElementById('smokeplus_status').innerHTML = '<i class="fas fa-cloud fa-stack-2x" style="color:rgb(150, 150, 150)" data-toggle="tooltip" data-placement="top" title="Smoke Plus OFF"></i><i class="fas fa-plus fa-stack-1x fa-inverse"></i>';
			//};

		},
		error: function() {
			console.log('Error: Failed to get current status from server.  Try: ' + errorCounter);
			errorCounter += 1;
			if (errorCounter > maxErrorCount) {
				$("#serverOfflineModal").modal('show');
			};
		}
	});
};

// Update the temperature for a specific probe/card 
function updateTempCard(label, temp) {
	idstring = label + "_temp";
	document.getElementById(idstring).innerHTML = temp;
};

// Initialize the notification target sliders for the notification modal
function initAllTargets() {
	// This function will initialize the target sliders for all notification modals so that they reflect the right current values
	for (item in notify_data) {

		initTarget(notify_data[item]);
	};
};

function initTarget(notify_item) {
	// This function will initialize the target sliders for an individual notification modal so that they reflect the right current values	
	//console.log('Init Target: ' + notify_item.label);
	var prefix = '';
	var postfix = '';
	if (notify_item.type == 'probe') {
		prefix = '';
		postfix = '_notify_temp';
	} else if (notify_data[item].type == 'probe_limit_high') {
		prefix = '_high_limit';
		postfix = '_limit_high_temp';
	} else if (notify_data[item].type == 'probe_limit_low') {
		prefix = '_low_limit';
		postfix = '_limit_low_temp';
	} else {
		return;
	};
	
	var outputTargetId = notify_item.label + prefix + '_tempOutputId';
	var inputTargetId = notify_item.label + prefix + '_tempInputId';
	var checkboxTargetId = notify_item.label + postfix;
	var targetValue = notify_item.target;
	var checkboxValue = notify_item.req;

	const rangeInput = document.getElementById(inputTargetId); 
	rangeInput.value = targetValue; 

	const textInput = document.getElementById(outputTargetId); 
	textInput.value = targetValue; 

	const checkboxInput = document.getElementById(checkboxTargetId);
	checkboxInput.checked = checkboxValue;
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
function updateNotificationCard(notify_info) {
	const label = notify_info.label;
	const req = notify_info.req;
	const shutdown = notify_info.shutdown;
	const keep_warm = notify_info.keep_warm;
	const target = notify_info.target;
	const type = notify_info.type; 
	const notify_btn_id = label + "_notify_btn";
	const eta_btn_id = label + "_eta_btn";
	var triggered = false;
	if ('triggered' in notify_info) {
		triggered = notify_info.triggered;
	};

	if ((type == 'probe') && (notify_status[label]['probe']))  {
		// Probe Notification Selected
		// Show the Notification Bell, Target Temp and the ETA 
	var eta = '<i class="fa-solid fa-spinner fa-spin-pulse"></i>';
	if (notify_info.eta != null) {
		eta = formatDuration(notify_info.eta);
	};
		document.getElementById(notify_btn_id).innerHTML = '<i class="far fa-bell"></i>&nbsp; ' + target + '&deg;' + units;
        document.getElementById(eta_btn_id).innerHTML = '<i class="fa-solid fa-hourglass-half"></i>&nbsp; ' + eta;
		document.getElementById(notify_btn_id).className = 'btn btn-sm btn-primary';
        $('#'+eta_btn_id).show();
	} else if ((!notify_status[label]['probe']) && ((notify_status[label]['probe_limit_high']) || (notify_status[label]['probe_limit_low']))) {
		// Other Notification Selected
		// Show the Notification Bell (Limit High / Low) Hide ETA
		document.getElementById(notify_btn_id).innerHTML = '<i class="far fa-bell"></i>'; 
		document.getElementById(notify_btn_id).className = 'btn btn-sm btn-primary';
		$('#'+eta_btn_id).hide();
	} else if ((type != 'probe') && (notify_status[label]['probe'])) {
		// Other Notification Cancelled (Probe Notification Selected)
		// Leave the Notification Bell, Target Temp and ETA shown
		document.getElementById(notify_btn_id).className = 'btn btn-sm btn-primary';
		$('#'+eta_btn_id).show();
	} else {
		// All Notifications Cancelled
		// Turn off the Notification Bell
		document.getElementById(notify_btn_id).innerHTML = '<i class="far fa-bell-slash"></i>';
		document.getElementById(notify_btn_id).className = 'btn btn-sm btn-outline-primary';
        $('#'+eta_btn_id).hide();
	};

	if (((notify_status[label]['probe_limit_high']) || (notify_status[label]['probe_limit_low'])) && (triggered)) {
		document.getElementById(notify_btn_id).className = 'btn btn-sm btn-danger';
	};
};

// Set Notification Request and Send to the Server
function setNotify(probe_label) {
	//console.log('Updating Notify Settings...')
	// Reset Action Settings 
	var shutdown = false;
	var keepWarm = false;
	var reignite = false;

	// Put current notify data into a new variable to update
	var updated_notify_data = JSON.parse(JSON.stringify(notify_data)); // Copy notify_data into a new variable

	// If simple notify on temperature is set, get the data and update the notification structure
	if ($("#"+probe_label +"_notify_temp").is(':checked')) {
		var target_temp = $("#"+probe_label+"_tempInputId").val();
		for (item in updated_notify_data) {
			if ((updated_notify_data[item].type == 'probe') && (updated_notify_data[item].label == probe_label)) {
			if ($("#"+probe_label +"_shutdown").is(':checked')){
				shutdown = true;
			};
			if ($("#"+probe_label +"_keepWarm").is(':checked')){
				keepWarm = true;
			};
			updated_notify_data[item].target = parseInt(target_temp);
			updated_notify_data[item].shutdown = shutdown;
			updated_notify_data[item].keep_warm = keepWarm;
			updated_notify_data[item].req = true;
			//console.log('Updated Simple Notify Temp Settings:');
			//console.log(updated_notify_data[item]);
			break;
			};
		};
	} else {
		// If simple notify is unchecked, then remove notification request. 
		for (item in updated_notify_data) {
			if ((updated_notify_data[item].type == 'probe') && (updated_notify_data[item].label == probe_label)) {
				updated_notify_data[item].req = false;
				break;
			};
		};
	};

	// Reset action variables
	shutdown = false;
	keepWarm = false;
	reignite = false;

	// If HIGH limit notify on temperature is set, get the data and update the notification structure
	if ($("#"+probe_label +"_limit_high_temp").is(':checked')) {
		var target_temp = $("#"+probe_label+"_high_limit_tempInputId").val();
		var current_temp = document.getElementById(probe_label+"_temp").innerHTML;
		for (item in updated_notify_data) {
			if ((updated_notify_data[item].type == 'probe_limit_high') && (updated_notify_data[item].label == probe_label)) {
				if ($("#"+probe_label +"_high_limit_shutdown").is(':checked')){
					shutdown = true;
				};
				updated_notify_data[item].target = parseInt(target_temp);
				updated_notify_data[item].shutdown = shutdown;
				updated_notify_data[item].req = true;
				// Mark as already triggered if the target value is greater than the current value
				if (parseInt(current_temp) > parseInt(target_temp)) {
					updated_notify_data[item].triggered = true;
				} else {
					updated_notify_data[item].triggered = false;
				};
				//console.log(probeGauges[probe_label].getValue());
				//console.log('Updated High Limit Notify Temp Settings:');
				//console.log(updated_notify_data[item]);
				break;
			};
		};
	} else {
		// If HIGH limit notify is unchecked, then remove notification request. 
		for (item in updated_notify_data) {
			if ((updated_notify_data[item].type == 'probe_limit_high') && (updated_notify_data[item].label == probe_label)) {
				updated_notify_data[item].req = false;
				break;
			};
		};
	};

	// Reset action variables
	shutdown = false;
	keepWarm = false;
	reignite = false;

	// If LOW limit notify on temperature is set, get the data and update the notification structure
	if ($("#"+probe_label +"_limit_low_temp").is(':checked')) {
		var target_temp = $("#"+probe_label+"_low_limit_tempInputId").val();
		var current_temp = document.getElementById(probe_label+"_temp").innerHTML;
		for (item in updated_notify_data) {
			if ((updated_notify_data[item].type == 'probe_limit_low') && (updated_notify_data[item].label == probe_label)) {
				if ($("#"+probe_label +"_low_limit_shutdown").is(':checked')){
					shutdown = true;
				};
				if ($("#"+probe_label +"_low_limit_shutdown").is(':checked')){
					reignite = true;
				};
				updated_notify_data[item].target = parseInt(target_temp);
				updated_notify_data[item].shutdown = shutdown;
				updated_notify_data[item].reignite = reignite;
				updated_notify_data[item].req = true;
				// Mark as already triggered if the target value is less than the current value
				if (parseInt(current_temp) < parseInt(target_temp)) {
					updated_notify_data[item].triggered = true;
				} else {
					updated_notify_data[item].triggered = false;
				};
				//console.log(probeGauges[probe_label].getValue());
				//console.log('Updated Low Limit Notify Temp Settings:');
				//console.log(updated_notify_data[item]);
				break;
			};
		};
	} else {
		// If LOW limit notify is unchecked, then remove notification request. 
		for (item in updated_notify_data) {
			if ((updated_notify_data[item].type == 'probe_limit_low') && (updated_notify_data[item].label == probe_label)) {
				updated_notify_data[item].req = false;
				break;
			};
		};
	};

    var postdata = { 
        'notify_data' : updated_notify_data
    };

	//console.log(updated_notify_data);

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
	dashLoadConfig();
	$("#dashSettingsModal").modal('show');
};

function dashLoadConfig() {
	$("#dash_config_card").load("/dash/config");
};

// Get dashboard data structure
function dashGetData() {
	req = $.ajax({
		url : '/api/settings',
		type : 'GET',
		success : function(settings){
			dashDataStruct = settings.settings.dashboard.dashboards.Basic;
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
				'Basic' : dashDataStruct
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

function dashClearErrorCounter() {
	errorCounter = 0;
};

// Main
$(document).ready(function(){
	// Setup Listeners 
	$('#reloadPage').click(function() {
		// Reload page when server side changes detected. 
		location.reload(); 
	});

	// Initialize Dashboard Data
	dashGetData();

	// Current temperature(s) loop
	probe_loop = setInterval(updateProbeCards, 500); // Update every 500ms 
    
	// Get initial hopper information 
	updateHopperStatus();
	
	// Current hopper information loop
	setInterval(updateHopperStatus, 30000);  // Update every 30000ms (30 seconds) 
});
