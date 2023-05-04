// GLOBALS
// Get units
var units = document.getElementById("units").value;
var temps_list;
var profiles;
var dc_temps_list;
var dc_profiles;

// Functions
function postSmartStartData(temps_list, profiles) {
	var postdata = {
		'temps_list': temps_list,
		'profiles': profiles,
	};

	$.ajax({
		url: '/settings/smartstart',
		type: 'POST',
		data: JSON.stringify(postdata),
		contentType: "application/json; charset=utf-8",
		traditional: true,
		success: function(data) {
			//console.log('POST data sent.');
		}
	});
};

function onDelete(td, rowSelected) {
	if (confirm('Are you sure to delete this record ?')) {
		if (rowSelected <= 1) {
			alert('Cannot delete last two profiles.  You must have at least one profile enabled.  Action cancelled.')
		} else if (rowSelected == profiles.length - 1) {
			// Select Row to Delete
			var delRow = td.parentElement.parentElement;
			// Select Previous Row
			var prevRow = delRow.previousElementSibling;
			document.getElementById("smartStartTable").deleteRow(delRow.rowIndex);
			console.log('Row ' + rowSelected + ' Deleted.');
			var delButtonHTML_enabled = '<button type="button" class="btn btn-danger btn-sm" id="sstrt_del_row" onClick="onDelete(this,' + (rowSelected - 1) + ')"><i class="fas fa-trash-alt"></i></button>';
			var delButtonHTML_disabled = '<button type="button" class="btn btn-secondary btn-sm" id="sstrt_del_row" data-toggle="tooltip" data-placement="top" title="This profile cannot be deleted." disabled><i class="fas fa-trash-alt"></i></button>';
			var prevEditButtonHTML = '<button type="button" class="btn btn-warning btn-sm" onClick="onEdit(' + (rowSelected - 1) + ')" data-toggle="modal" data-target="#sstrt_edit_modal"><i class="fas fa-edit"></i></button> \n';
			// If it's the previous profile is the second profile, disable the delete button
			if (rowSelected - 1 == 1) {
				var delButtonHTML = delButtonHTML_disabled;
			} else {
				var delButtonHTML = delButtonHTML_enabled;
			};
			prevRow.cells[0].innerHTML = prevEditButtonHTML + delButtonHTML;
			if (rowSelected > 1) {
				prevRow.cells[1].innerHTML = '&gt ' + temps_list[rowSelected - 2] + units;
				var newMinTemp = temps_list[rowSelected - 2] + 1;
			} else {
				prevRow.cells[1].innerHTML = '&gt ' + temps_list[rowSelected - 1] + units;
				var newMinTemp = temps_list[rowSelected - 1] + 1;
			}

			// Change minimum value for added items
			$('#minTemp').val(newMinTemp);
			document.getElementById("minTemp").min = newMinTemp;
			$('#addMinTemp').html(newMinTemp - 1);

			// Remove items from lists
			if (rowSelected > 1) {
				var popped = temps_list.pop();
				console.log('Popped: ' + popped);
			}
			profiles.pop();

			// Save values to server
			postSmartStartData(temps_list, profiles);
		};
	};
};

function onEdit(rowSelected) {
	if (rowSelected == 0) {
		// First Row Selected
		var minTemp = 0;
		var curTemp = temps_list[0];
		if (temps_list.length > 1) {
			var maxTemp = temps_list[1] - 1;
		} else {
			var maxTemp = 1000;
		}
		document.getElementById("edit_minTemp").disabled = '';
	} else if (rowSelected == profiles.length - 1) {
		// Last Row Selected
		// Disable editing min Temp
		var minTemp = temps_list[rowSelected - 1];
		var curTemp = temps_list[rowSelected - 1];
		var maxTemp = minTemp;
		document.getElementById("edit_minTemp").disabled = 'disabled';
	} else if (rowSelected == profiles.length - 2) {
		// Second to Last Row Selected
		var minTemp = temps_list[rowSelected - 1] + 1;
		var curTemp = temps_list[rowSelected];
		var maxTemp = 1000;
		document.getElementById("edit_minTemp").disabled = '';
	} else {
		// All other rows
		var minTemp = temps_list[rowSelected - 1] + 1;
		var curTemp = temps_list[rowSelected];
		var maxTemp = temps_list[rowSelected + 1] - 1;
		document.getElementById("edit_minTemp").disabled = '';
	}
	var startupTime = profiles[rowSelected].startuptime;
	var augeronTime = profiles[rowSelected].augerontime;
	var pMode = profiles[rowSelected].p_mode;

	$('#edit_minTemp').val(curTemp);
	document.getElementById("edit_minTemp").min = minTemp;
	document.getElementById("edit_minTemp").max = maxTemp;

	$('#edit_startupTime').val(startupTime);
	$('#edit_augeronTime').val(augeronTime);
	$('#edit_pMode').val(pMode);
	$('#saveEdits').val(rowSelected);
	if (rowSelected == profiles.length - 1) {
		$('#edit_RangeText').html('No minimum temperature for the last profile.');
	} else {
		$('#edit_RangeText').html('Enter a value in the range <span id="editRangeMin">0</span>-<span id="editRangeMax">200</span>' + units);
		$('#editRangeMin').html(minTemp);
		$('#editRangeMax').html(maxTemp);
	};

	//console.log('Row Selected for Edit: ' + rowSelected);
};

function saveChanges(rowSelectedString) {
	rowSelected = parseInt(rowSelectedString);

	// Validate
	var newTemp = parseInt($('#edit_minTemp').val());
	var valid = false;

	// Check minTemp Value
	if ((rowSelected == 0) && (temps_list.length > 1)) {
		// If first row selected, and temperature list is longer than 1 set point
		if ((newTemp >= 0) && (newTemp < temps_list[1])) {
			valid = true;
		};
	} else if ((rowSelected == 0) && (temps_list.length == 1)) {
		// If first row selected, and there is only one set point
		valid = true;
	} else if (rowSelected == profiles.length - 1) {
		// If last profile is selected
		newTemp = temps_list[rowSelected - 1];
		valid = true;
	} else if ((newTemp > temps_list[rowSelected - 1]) && (newTemp < temps_list[rowSelected + 1])) {
		// If inner rows are selected, check range
		valid = true;
	} else if ((newTemp > temps_list[rowSelected - 1]) && (rowSelected + 1 == temps_list.length)) {
		// If second to last row is selected check greater than previous
		valid = true;
	} else {
		valid = false;
		console.log('Failed Temperature Range Check.');
	};

	// Check startup time
	var startuptime = parseInt($('#edit_startupTime').val());

	if ((startuptime < 30) || (startuptime > 1200)) {
		valid = false;
		console.log('Failed Startup Time Range Check.');
	};

	var augerontime = parseInt($('#edit_augeronTime').val());

	if ((augerontime < 1) || (augerontime > 1000)) {
		valid = false;
		console.log('Failed Auger On Time Range Check.');
	}

	var p_mode = parseInt($('#edit_pMode').val());

	if ((p_mode < 0) || (p_mode > 9)) {
		valid = false;
		console.log('Failed P-Mode Range Check.');
	}

	// If checks passed, send to server and update table
	if (valid) {
		// Get data and send to server
		if (rowSelected < profiles.length - 1) {
			temps_list[rowSelected] = newTemp;
		};

		profiles[rowSelected].startuptime = startuptime;
		profiles[rowSelected].augerontime = augerontime;
		profiles[rowSelected].p_mode = p_mode;
		postSmartStartData(temps_list, profiles);

		// Update table with new data
		var table = document.getElementById("smartStartTable").getElementsByTagName('tbody')[0];
		var updateRow = table.rows[rowSelected];

		if (rowSelected == 0) {
			// First row selected format with less than
			updateRow.cells[1].innerHTML = newTemp + units + ' &lt';
			if (profiles.length > 1) {
				var nextRow = table.rows[rowSelected + 1];
				var nextTemp = temps_list[rowSelected + 1];
				nextRow.cells[1].innerHTML = newTemp + units + ' - ' + nextTemp + units;
			};
		} else if (rowSelected == profiles.length - 1) {
			updateRow.cells[1].innerHTML = '&gt ' + newTemp + units;
		} else {
			// Middle rows format
			prevTemp = temps_list[rowSelected - 1];
			updateRow.cells[1].innerHTML = prevTemp + units + ' - ' + newTemp + units;
			if (rowSelected == profiles.length - 2) {
				// Second to last row selected format next row with greater than
				var nextRow = table.rows[rowSelected + 1];
				nextRow.cells[1].innerHTML = '&gt ' + newTemp + units;
			} else if (profiles.length > 1) {
				var nextRow = table.rows[rowSelected + 1];
				var nextTemp = temps_list[rowSelected + 1];
				nextRow.cells[1].innerHTML = newTemp + units + ' - ' + nextTemp + units;
			};
		};

		updateRow.cells[2].innerHTML = startuptime + 's';
		updateRow.cells[3].innerHTML = augerontime + 's';
		updateRow.cells[4].innerHTML = p_mode;

		// Update Add Modal minTemp
		if (rowSelected == temps_list.length) {
			var newMinTemp = temps_list[rowSelected - 1] + 1;
			$('#minTemp').val(newMinTemp);
			document.getElementById("minTemp").min = newMinTemp;
			$('#addMinTemp').html(newMinTemp - 1);
		};
	} else {
		alert('Invalid Input Range for one of your values.  No changes saved.  Please try again.');
	};
};

function addSmartStartProfile(data) {
	var table = document.getElementById("smartStartTable").getElementsByTagName('tbody')[0];
	var newRow = table.insertRow(table.length);
	var lastRow = newRow.previousElementSibling;
	var editButtonHTML = '<button type="button" class="btn btn-warning btn-sm" onClick="onEdit(' + data.rowSelected + ')" data-toggle="modal" data-target="#sstrt_edit_modal"><i class="fas fa-edit"></i></button> \n';
	var delButtonHTML_enabled = '<button type="button" class="btn btn-danger btn-sm" id="sstrt_del_row" onClick="onDelete(this,' + data.rowSelected + ')"><i class="fas fa-trash-alt"></i></button>';
	var delButtonHTML_disabled = '<button type="button" class="btn btn-secondary btn-sm" id="sstrt_del_row" data-toggle="tooltip" data-placement="top" title="This profile cannot be deleted." disabled><i class="fas fa-trash-alt"></i></button>';

	if (data.position == 'first' || data.position == 'inner') {
		cell0 = newRow.insertCell(0);
		cell0.innerHTML = editButtonHTML + delButtonHTML_disabled;
	} else {
		cell0 = newRow.insertCell(0);
		cell0.innerHTML = editButtonHTML + delButtonHTML_enabled;
	}
	if (data.position == 'first') {
		cell1 = newRow.insertCell(1);
		cell1.innerHTML = data.tempMin + units + ' &lt';
	} else if (data.position == 'last') {
		cell1 = newRow.insertCell(1);
		cell1.innerHTML = '&gt ' + data.tempMin + units;
		// Edit Previous Cells Buttons and Data
		var prevEditButtonHTML = '<button type="button" class="btn btn-warning btn-sm" onClick="onEdit(' + (data.rowSelected - 1) + ')" data-toggle="modal" data-target="#sstrt_edit_modal"><i class="fas fa-edit"></i></button> \n';
		lastRow.cells[0].innerHTML = prevEditButtonHTML + delButtonHTML_disabled;
		lastRow.cells[1].innerHTML = data.tempMinPrevious + units + ' - ' + data.tempMin + units;
	} else {
		cell1 = newRow.insertCell(1);
		cell1.innerHTML = data.tempMinPrevious + units + ' - ' + data.tempMin + units;
	}
	cell2 = newRow.insertCell(2);
	cell2.innerHTML = data.startUpTime + 's';
	cell3 = newRow.insertCell(3);
	cell3.innerHTML = data.augerOnTime + 's';
	cell4 = newRow.insertCell(4);
	cell4.innerHTML = data.pMode;
};

function onAdd() {
	var newRowNum = profiles.length;

	if (temps_list.length > 1) {
		var prevMinTemp = temps_list[newRowNum - 2];
	} else {
		var prevMinTemp = temps_list[0];
	}

	// Validate Inputs
	var valid = true;

	// Check startup time
	var startuptime = parseInt($('#startupTime').val());

	if ((startuptime < 30) || (startuptime > 1200)) {
		valid = false;
		console.log('Failed Startup Time Range Check.');
	};

	var augerontime = parseInt($('#augeronTime').val());

	if ((augerontime < 1) || (augerontime > 1000)) {
		valid = false;
		console.log('Failed Auger On Time Range Check.');
	}

	var p_mode = parseInt($('#pMode').val());

	if ((p_mode < 0) || (p_mode > 9)) {
		valid = false;
		console.log('Failed P-Mode Range Check.');
	}

	// If checks passed, send to server and update table
	if (valid) {
		if (parseInt($("#minTemp").val()) > prevMinTemp) {
			profiles[newRowNum] = {};
			profiles[newRowNum].startuptime = parseInt($("#startupTime").val());
			profiles[newRowNum].p_mode = parseInt($("#pMode").val());
			profiles[newRowNum].augerontime = parseInt($("#augeronTime").val());

			temps_list[newRowNum - 1] = parseInt($("#minTemp").val());
			postSmartStartData(temps_list, profiles);
			// Add HTML
			profile = {}
			profile.rowSelected = newRowNum;
			profile.numRows = profiles.length;
			profile.position = 'last';
			profile.tempMinPrevious = prevMinTemp
			profile.tempMin = temps_list[newRowNum - 1];

			var newMinTemp = profile.tempMin + 1;
			$('#minTemp').val(newMinTemp);
			document.getElementById("minTemp").min = newMinTemp;
			$('#addMinTemp').html(newMinTemp - 1);

			profile.startUpTime = profiles[newRowNum].startuptime;
			profile.augerOnTime = profiles[newRowNum].augerontime;
			profile.pMode = profiles[newRowNum].p_mode;
			addSmartStartProfile(profile);
		} else {
			alert('Minimum Temperature MUST be greater than the previous minimum temperature!  Not added.');
		};
	} else {
		alert('Invalid Input Range for one of your values.  No changes saved.  Please try again.');
	};
};

function postPWMDutyCycleData(dc_temps_list, dc_profiles) {
	var post_data = {
		'dc_temps_list': dc_temps_list,
		'dc_profiles': dc_profiles,
	};

	$.ajax({
		url: '/settings/pwm_duty_cycle',
		type: 'POST',
		data: JSON.stringify(post_data),
		contentType: "application/json; charset=utf-8",
		traditional: true,
		success: function(data) {
			//console.log('POST data sent.');
		}
	});
};

function onDeletePWM(td, rowSelected) {
	if (confirm('Are you sure to delete this record ?')) {
		if (rowSelected <= 1) {
			alert('Cannot delete last two profiles.  You must have at least one profile enabled.  Action cancelled.')
		} else if (rowSelected == dc_profiles.length - 1) {
			// Select Row to Delete
			var delRow = td.parentElement.parentElement;
			// Select Previous Row
			var prevRow = delRow.previousElementSibling;
			document.getElementById("duty_cycle_table").deleteRow(delRow.rowIndex);
			console.log('Row ' + rowSelected + ' Deleted.');
			var delButtonHTML_enabled = '<button type="button" class="btn btn-danger btn-sm" id="dc_del_row" onClick="onDeletePWM(this,' + (rowSelected - 1) + ')"><i class="fas fa-trash-alt"></i></button>';
			var delButtonHTML_disabled = '<button type="button" class="btn btn-secondary btn-sm" id="dc_del_row" data-toggle="tooltip" data-placement="top" title="This profile cannot be deleted." disabled><i class="fas fa-trash-alt"></i></button>';
			var prevEditButtonHTML = '<button type="button" class="btn btn-warning btn-sm" onClick="onEditPWM(' + (rowSelected - 1) + ')" data-toggle="modal" data-target="#dc_edit_modal"><i class="fas fa-edit"></i></button> \n';
			// If it's the previous profile is the second profile, disable the delete button
			if (rowSelected - 1 == 1) {
				var delButtonHTML = delButtonHTML_disabled;
			} else {
				var delButtonHTML = delButtonHTML_enabled;
			};
			prevRow.cells[0].innerHTML = prevEditButtonHTML + delButtonHTML;
			if (rowSelected > 1) {
				prevRow.cells[1].innerHTML = '&gt ' + dc_temps_list[rowSelected - 2] + units;
				var newMinTemp = dc_temps_list[rowSelected - 2] + 1;
			} else {
				prevRow.cells[1].innerHTML = '&gt ' + dc_temps_list[rowSelected - 1] + units;
				var newMinTemp = dc_temps_list[rowSelected - 1] + 1;
			}

			// Change minimum value for added items
			$('#dc_temp').val(newMinTemp);
			document.getElementById("dc_temp").min = newMinTemp;
			$('#dc_add_temp').html(newMinTemp - 1);

			// Remove items from lists
			if (rowSelected > 1) {
				var popped = dc_temps_list.pop();
				console.log('Popped: ' + popped);
			}
			dc_profiles.pop();

			// Save values to server
			postPWMDutyCycleData(dc_temps_list, dc_profiles);
		};
	};
};

function onEditPWM(rowSelected) {
	if (rowSelected == 0) {
		// First Row Selected
		var minTemp = 0;
		var curTemp = dc_temps_list[0];
		if (dc_temps_list.length > 1) {
			var maxTemp = dc_temps_list[1] - 1;
		} else {
			var maxTemp = 100;
		}
		document.getElementById("dc_edit_temp").disabled = '';
	} else if (rowSelected == dc_profiles.length - 1) {
		// Last Row Selected
		// Disable editing Temp
		var minTemp = dc_temps_list[rowSelected - 1];
		var curTemp = dc_temps_list[rowSelected - 1];
		var maxTemp = minTemp;
		document.getElementById("dc_edit_temp").disabled = 'disabled';
	} else if (rowSelected == dc_profiles.length - 2) {
		// Second to Last Row Selected
		var minTemp = dc_temps_list[rowSelected - 1] + 1;
		var curTemp = dc_temps_list[rowSelected];
		var maxTemp = 100;
		document.getElementById("dc_edit_temp").disabled = '';
	} else {
		// All other rows
		var minTemp = dc_temps_list[rowSelected - 1] + 1;
		var curTemp = dc_temps_list[rowSelected];
		var maxTemp = dc_temps_list[rowSelected + 1] - 1;
		document.getElementById("dc_edit_temp").disabled = '';
	}
	var duty_cycle = dc_profiles[rowSelected].duty_cycle;

	$('#dc_edit_temp').val(curTemp);
	document.getElementById("dc_edit_temp").min = minTemp;
	document.getElementById("dc_edit_temp").max = maxTemp;

	$('#dc_edit_duty_cycle').val(duty_cycle);
	$('#dc_save_edits').val(rowSelected);
	if (rowSelected == dc_profiles.length - 1) {
		$('#dc_edit_range_text').html('Temperature cannot be changed for the last profile.');
	} else {
		$('#dc_edit_range_text').html('Enter a value in the range <span id="dc_edit_range_min">0</span>-<span id="dc_edit_range_max">100</span>' + units);
		$('#dc_edit_range_min').html(minTemp);
		$('#dc_edit_range_max').html(maxTemp);
	};

	//console.log('Row Selected for Edit: ' + rowSelected);
};

function saveChangesPWM(rowSelectedString) {
	rowSelected = parseInt(rowSelectedString);

	// Validate
	var newTemp = parseInt($('#dc_edit_temp').val());
	var valid = false;

	// Check minTemp Value
	if ((rowSelected == 0) && (dc_temps_list.length > 1)) {
		// If first row selected, and temperature list is longer than 1 set point
		if ((newTemp >= 0) && (newTemp < dc_temps_list[1])) {
			valid = true;
		};
	} else if ((rowSelected == 0) && (dc_temps_list.length == 1)) {
		// If first row selected, and there is only one set point
		valid = true;
	} else if (rowSelected == dc_profiles.length - 1) {
		// If last profile is selected
		newTemp = dc_temps_list[rowSelected - 1];
		valid = true;
	} else if ((newTemp > dc_temps_list[rowSelected - 1]) && (newTemp < dc_temps_list[rowSelected + 1])) {
		// If inner rows are selected, check range
		valid = true;
	} else if ((newTemp > dc_temps_list[rowSelected - 1]) && (rowSelected + 1 == dc_temps_list.length)) {
		// If second to last row is selected check greater than previous
		valid = true;
	} else {
		valid = false;
		console.log('Failed Temperature Range Check.');
	};

	// Check Duty Cycle
	var duty_cycle = parseInt($('#dc_edit_duty_cycle').val());

	if ((duty_cycle < 1) || (duty_cycle > 100)) {
		valid = false;
		console.log('Failed Duty Cycle Check.');
	};

	// If checks passed, send to server and update table
	if (valid) {
		// Get data and send to server
		if (rowSelected < dc_profiles.length - 1) {
			dc_temps_list[rowSelected] = newTemp;
		};

		dc_profiles[rowSelected].duty_cycle = duty_cycle;
		postPWMDutyCycleData(dc_temps_list, dc_profiles);

		// Update table with new data
		var table = document.getElementById("duty_cycle_table").getElementsByTagName('tbody')[0];
		var updateRow = table.rows[rowSelected];

		if (rowSelected == 0) {
			// First row selected format with less than
			updateRow.cells[1].innerHTML = newTemp + units + ' &lt';
			if (dc_profiles.length > 1) {
				var nextRow = table.rows[rowSelected + 1];
				var nextTemp = dc_temps_list[rowSelected + 1];
				nextRow.cells[1].innerHTML = newTemp + units + ' - ' + nextTemp + units;
			};
		} else if (rowSelected == dc_profiles.length - 1) {
			updateRow.cells[1].innerHTML = '&gt ' + newTemp + units;
		} else {
			// Middle rows format
			prevTemp = dc_temps_list[rowSelected - 1];
			updateRow.cells[1].innerHTML = prevTemp + units + ' - ' + newTemp + units;
			if (rowSelected == dc_profiles.length - 2) {
				// Second to last row selected format next row with greater than
				var nextRow = table.rows[rowSelected + 1];
				nextRow.cells[1].innerHTML = '&gt ' + newTemp + units;
			} else if (dc_profiles.length > 1) {
				var nextRow = table.rows[rowSelected + 1];
				var nextTemp = dc_temps_list[rowSelected + 1];
				nextRow.cells[1].innerHTML = newTemp + units + ' - ' + nextTemp + units;
			};
		};

		updateRow.cells[2].innerHTML = duty_cycle + '%';

		// Update Add Modal minTemp
		if (rowSelected == dc_temps_list.length) {
			var newMinTemp = dc_temps_list[rowSelected - 1] + 1;
			$('#dc_temp').val(newMinTemp);
			document.getElementById("dc_temp").min = newMinTemp;
			$('#dc_add_temp').html(newMinTemp - 1);
		};
	} else {
		alert('Invalid Input Range for one of your values.  No changes saved.  Please try again.');
	};
};

function addPWMProfile(data) {
	var table = document.getElementById("duty_cycle_table").getElementsByTagName('tbody')[0];
	var newRow = table.insertRow(table.length);
	var lastRow = newRow.previousElementSibling;
	var editButtonHTML = '<button type="button" class="btn btn-warning btn-sm" onClick="onEditPWM(' + data.rowSelected + ')" data-toggle="modal" data-target="#dc_edit_modal"><i class="fas fa-edit"></i></button> \n';
	var delButtonHTML_enabled = '<button type="button" class="btn btn-danger btn-sm" id="dc_del_row" onClick="onDeletePWM(this,' + data.rowSelected + ')"><i class="fas fa-trash-alt"></i></button>';
	var delButtonHTML_disabled = '<button type="button" class="btn btn-secondary btn-sm" id="dc_del_row" data-toggle="tooltip" data-placement="top" title="This profile cannot be deleted." disabled><i class="fas fa-trash-alt"></i></button>';

	if (data.position == 'first' || data.position == 'inner') {
		cell0 = newRow.insertCell(0);
		cell0.innerHTML = editButtonHTML + delButtonHTML_disabled;
	} else {
		cell0 = newRow.insertCell(0);
		cell0.innerHTML = editButtonHTML + delButtonHTML_enabled;
	}
	if (data.position == 'first') {
		cell1 = newRow.insertCell(1);
		cell1.innerHTML = data.tempMin + units + ' &lt';
	} else if (data.position == 'last') {
		cell1 = newRow.insertCell(1);
		cell1.innerHTML = '&gt ' + data.tempMin + units;
		// Edit Previous Cells Buttons and Data
		var prevEditButtonHTML = '<button type="button" class="btn btn-warning btn-sm" onClick="onEditPWM(' + (data.rowSelected - 1) + ')" data-toggle="modal" data-target="#dc_edit_modal"><i class="fas fa-edit"></i></button> \n';
		lastRow.cells[0].innerHTML = prevEditButtonHTML + delButtonHTML_disabled;
		lastRow.cells[1].innerHTML = data.tempMinPrevious + units + ' - ' + data.tempMin + units;
	} else {
		cell1 = newRow.insertCell(1);
		cell1.innerHTML = data.tempMinPrevious + units + ' - ' + data.tempMin + units;
	}
	cell2 = newRow.insertCell(2);
	cell2.innerHTML = data.duty_cycle + '%';
};

function onAddPWM() {
	var newRowNum = dc_profiles.length;

	if (dc_temps_list.length > 1) {
		var prevMinTemp = dc_temps_list[newRowNum - 2];
	} else {
		var prevMinTemp = dc_temps_list[0];
	}

	// Validate Inputs
	var valid = true;

	// Check startup time
	var duty_cycle = parseInt($('#dc_duty_cycle').val());

	if ((duty_cycle < 1) || (duty_cycle > 100)) {
		valid = false;
		console.log('Failed Duty Cycle Check.');
	};

	// If checks passed, send to server and update table
	if (valid) {
		if (parseInt($("#dc_temp").val()) > prevMinTemp) {
			dc_profiles[newRowNum] = {};
			dc_profiles[newRowNum].duty_cycle = parseInt($("#dc_duty_cycle").val());

			dc_temps_list[newRowNum - 1] = parseInt($("#dc_temp").val());
			postPWMDutyCycleData(dc_temps_list, dc_profiles);
			// Add HTML
			profile = {}
			profile.rowSelected = newRowNum;
			profile.numRows = dc_profiles.length;
			profile.position = 'last';
			profile.tempMinPrevious = prevMinTemp
			profile.tempMin = dc_temps_list[newRowNum - 1];

			var newMinTemp = profile.tempMin + 1;
			$('#dc_temp').val(newMinTemp);
			document.getElementById("dc_temp").min = newMinTemp;
			$('#dc_add_temp').html(newMinTemp - 1);

			profile.duty_cycle = dc_profiles[newRowNum].duty_cycle;
			addPWMProfile(profile);
		} else {
			alert('Temperature MUST be greater than the previous temperature!  Not added.');
		};
	} else {
		alert('Invalid Input Range for one of your values.  No changes saved.  Please try again.');
	};
};

// Function to change the controller card selected 
$('#selectController').on('change', function() {
	$('#controller_config').load("/settings/controller_card", {"selected" : this.value});
});

// On page load...
$(document).ready(function() {
	// Setup Color Picker for all elements whose id starts with 'clrpck_'
	$(function () {
		$('[id^="clrpck_"]').colorpicker();
	});
	// Select last nav pill
	$('a[data-toggle="pill"]').on('show.bs.tab', function(e) {
		sessionStorage.setItem('activeTab', $(e.target).attr('href'));
	});
	var activeTab = sessionStorage.getItem('activeTab');
	if (activeTab) {
		$('#v-pills-tab a[href="' + activeTab + '"]').tab('show');
	}

	// Prevent 'enter' from doing a form submit
	$(window).keydown(function(event) {
		if (event.keyCode == 13) {
			event.preventDefault();
			return false;
		}
	});

	// Get Smart Start Data
	$.ajax({
		url: '/settings/smartstart',
		type: 'GET',
		contentType: "application/json; charset=utf-8",
		traditional: true,
		success: function(data) {
			temps_list = data.temps_list;
			profiles = data.profiles;
			// Populate table with initial data
			var profile = {};
			for (let index = 0; index < profiles.length; index++) {
				profile.rowSelected = index;
				profile.numRows = profiles.length;
				// Determine list position
				if (index == 0) {
					profile.position = 'first';
				} else if (index == profiles.length - 1) {
					profile.position = 'last';
				} else {
					profile.position = 'inner';
				}
				// Set previous temperature minimum value, for ranges
				if (index > 0) {
					profile.tempMinPrevious = temps_list[index - 1];
				} else {
					profile.tempMinPrevious = temps_list[index];
				}
				// If last profile and the list is greater than 1 profile long
				if ((index == profiles.length - 1) && (profiles.length > 1)) {
					profile.tempMin = temps_list[index - 1];
					profile.tempMinPrevious = temps_list[index - 2];
					// Set minimum value for next range to be the minimum of last range plus 1
					var newMinTemp = temps_list[index - 1] + 1;
					$('#minTemp').val(newMinTemp);
					document.getElementById("minTemp").min = newMinTemp;
					$('#addMinTemp').html(newMinTemp - 1);
				} else {
					profile.tempMin = temps_list[index];
				};
				profile.startUpTime = profiles[index].startuptime;
				profile.augerOnTime = profiles[index].augerontime;
				profile.pMode = profiles[index].p_mode;
				addSmartStartProfile(profile);
			}
		}
	});

	if(dc_fan_enabled == 'True') {
		// Get PWM Duty Cycle Data
		$.ajax({
			url: '/settings/pwm_duty_cycle',
			type: 'GET',
			contentType: "application/json; charset=utf-8",
			traditional: true,
			success: function(data) {
				dc_temps_list = data.dc_temps_list;
				dc_profiles = data.dc_profiles;
				// Populate table with initial data
				var profile = {};
				for (let index = 0; index < dc_profiles.length; index++) {
					profile.rowSelected = index;
					profile.numRows = dc_profiles.length;
					// Determine list position
					if (index == 0) {
						profile.position = 'first';
					} else if (index == dc_profiles.length - 1) {
						profile.position = 'last';
					} else {
						profile.position = 'inner';
					}
					// Set previous temperature minimum value, for ranges
					if (index > 0) {
						profile.tempMinPrevious = dc_temps_list[index - 1];
					} else {
						profile.tempMinPrevious = dc_temps_list[index];
					}
					// If last profile and the list is greater than 1 profile long
					if ((index == dc_profiles.length - 1) && (dc_profiles.length > 1)) {
						profile.tempMin = dc_temps_list[index - 1];
						profile.tempMinPrevious = dc_temps_list[index - 2];
						// Set minimum value for next range to be the minimum of last range plus 1
						var newMinTemp = dc_temps_list[index - 1] + 1;
						$('#dc_temp').val(newMinTemp);
						document.getElementById("dc_temp").min = newMinTemp;
						$('#dc_add_temp').html(newMinTemp - 1);
					} else {
						profile.tempMin = dc_temps_list[index];
					};
					profile.duty_cycle = dc_profiles[index].duty_cycle;
					addPWMProfile(profile);
				}
			}
		});
	};

    $('button[name=addAppriseLocation]').click(function(e) {
        e.preventDefault();
        $('.appriselocation').last().clone(true) //set withDataAndEvents to true in .clone to include event handlers
            .find("input:text").val("").end()
            .insertAfter($('.appriselocation').last());
    });

    $('button[name=appriseDeleteRow]').click(function(e) {
        e.preventDefault();
        if($(this).parent().parent().find("input:text").val().length > 0) {
            if(confirm('Row is not empty, are you sure?')) { //input has text in it, verify
                if($('.appriselocation').length > 1) { //only delete if more than row, keeps interface readier for use
                    $(this).parent().parent().remove();
                }
                else {
                    $(this).parent().parent().find("input:text").val("")
                }
            }
        }
        else if($('.appriselocation').length > 1) { //only delete if more than row, keeps interface readier for use
            $(this).parent().parent().remove();

        }
    });

	$('#after_startup_mode').change(function() {
		var mode = $('#after_startup_mode').val();
		if(mode == 'Hold') {
			$('#startup_hold_value_input').slideDown();
		} else {
			$('#startup_hold_value_input').slideUp();
		};
	});

}); // End of document ready function