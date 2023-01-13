// Probes Configuration Javascript

// Global Variables
var deviceNameSelected = '';
var deviceModuleSelected = '';
var probeNameSelected = '';

//
// Device Functions
//

// Select a Device
function probe_selectDevice(deviceName) {
	deviceNameSelected = deviceName;
};

// Delete the Selected Device
function probe_deleteDevice(modalName) {
	// Delay the delete command for 500ms, so that the modal can close down
	var send_delayed_cmd = setInterval(function(){
		$('#probeDevicesCard').load("/probeconfig", {"action" : "delete_device", "section" : "devices", "name" : deviceNameSelected});
		clearInterval(send_delayed_cmd);
		$('#probePortsCard').load("/probeconfig", {"action" : "refresh_probes", "section" : "ports"});
	}, 500);
};

// Load Device Module Configuration / Settings into modal 
function probe_addShowDeviceConfig(module) {
	deviceModuleSelected = module;
	//load module information into modal
	$('#addProbeDeviceField').load("/probeconfig", {"action" : "add_config", "section" : "devices", "module" : deviceModuleSelected});
};

function probe_addSubmitDeviceConfig() {
	var send_delayed_cmd = setInterval(function(){
		//get device_module type from the select box
		var device_name = $("#probeDeviceNameAdd").val();

		//get all configuration data 
		var response = {};

		const collection = document.getElementsByClassName("deviceSpecificAdd");
		for (let i = 0; i < collection.length; i++) {
			var setting_id = collection[i].id;
			var setting_val = $('#'+setting_id).val();
			response[setting_id] = setting_val;
		}
		response['action'] = 'add_device';
		response['section'] = 'devices';
		response['name'] = device_name;
		response['module'] = deviceModuleSelected;

		$('#probeDevicesCard').load("/probeconfig", response);
		clearInterval(send_delayed_cmd);
		$('#addProbeDeviceField').html('');
	}, 500);
};

function probe_editShowDeviceConfig(deviceName) {
	deviceNameSelected = deviceName;
	//load module information into modal
	$('#editProbeDeviceField').load("/probeconfig", {"action" : "edit_config", "section" : "devices", "name" : deviceName});
};

function probe_editSubmitDeviceConfig() {
	var send_delayed_cmd = setInterval(function(){
		var new_device_name = $("#probeDeviceNameEdit").val();

		//get all configuration data 
		var response = {};

		const collection = document.getElementsByClassName("deviceSpecificEdit");
		for (let i = 0; i < collection.length; i++) {
			var setting_id = collection[i].id;
			var setting_val = $('#'+setting_id).val();
			response[setting_id] = setting_val;
		}
		response['action'] = 'edit_device';
		response['section'] = 'devices';
		response['name'] = deviceNameSelected;
		response['newname'] = new_device_name;
		response['module'] = deviceModuleSelected;

		$('#probeDevicesCard').load("/probeconfig", response);
		clearInterval(send_delayed_cmd);
		// After getting values, clear data so that it doesn't interfere with other data
		$('#editProbeDeviceField').html('');
	}, 500);
};

// 
// Probe / Port Functions 
// 

// Select a Device
function probe_selectProbe(probeName) {
	probeNameSelected = probeName;
	console.log('Selecting: ' + probeNameSelected);
};

// Delete the Selected Device
function probe_deleteProbe() {
	console.log('Deleting Port/Probe: ' + probeNameSelected);
	// Delay the delete command for 500ms, so that the modal can close down
	var send_delayed_cmd = setInterval(function(){
		$('#probePortsCard').load("/probeconfig", {"action" : "delete_probe", "section" : "ports", "label" : probeNameSelected});
		clearInterval(send_delayed_cmd);
	}, 500);
};

// Load Device Module Configuration / Settings into modal 
function probe_showProbeConfig(probeName) {
	console.log('Showing Port/Probe Configuration');
	probeNameSelected = probeName;
	//load module information into modal
	if (probeName == '') {
		fieldName = '#addProbePortField';		
	} else {
		fieldName = '#editProbePortField';		
	};
	$(fieldName).load("/probeconfig", {"action" : "config", "section" : "ports", "label" : probeName});
};

// Submit probe config (add/edit)
function probe_submitProbeConfig(request) {
	if (request == 'add') {
		console.log('Adding Port/Probe.');
		// Clear the EDIT probe modal so that it doesn't interfere with getting data. 
		$('#editProbePortField').html('');
	} else {
		console.log('Editing Port/Probe.');
		// Clear the ADD probe modal so that it doesn't interfere with getting data. 
		$('#addProbePortField').html('');
	};

	var send_delayed_cmd = setInterval(function(){
		//get all configuration data 
		var response = {};

		const collection = document.getElementsByClassName("probeConfig");
		for (let i = 0; i < collection.length; i++) {
			var setting_id = collection[i].id;
			var setting_val = $('#'+setting_id).val();
			response[setting_id] = setting_val;
		}

		if (request == 'add') {
			response['action'] = 'add_probe';
		} else {
			response['action'] = 'edit_probe';
		};
		
		response['section'] = 'ports';
		response['name'] = probeNameSelected;

		$('#probePortsCard').load("/probeconfig", response);

		// After getting values, clear data so that it doesn't interfere with other data
		$('#editProbePortField').html('');
		$('#addProbePortField').html('');

		clearInterval(send_delayed_cmd);
	}, 500);
};

