// Timer Bar JS

// Global Variables 

var timerStart = 0;
var timerPaused = 0;
var timerEnd = 0;
var timerShutdown = false;
var timerKeepWarm = false;
var timerFinishedFlag = false;
var timerUpdateTimerValue ;  // Interval used to refresh the displayed time
var timerUpdateTimerStatus ;  // Interval used to get the timer status
var timerSuppressUpdate = false;  // Suppress update to timer buttons right after a button click
var timerUserHidden = false;  // Flag that keeps the timer hidden if the user chose hidden

// Toggles visibility of the timer status in the top-bar (triggered by pressing button in navbar)
function timerToggle() {
	if ($("#toggleTimer").html() == 'hidden') {
		timerUserHidden = false;
		$("#timer_bar").slideDown();
		$("#toggleTimer").html('unhidden');
	} else {
		timerUserHidden = true;
		$("#timer_bar").slideUp();
		$("#toggleTimer").html('hidden');
	};
};

function timerModal() {
	// Show timer settings modal 
	$('#timerModal').modal('show');
};

function timerSecondsRemaining(timerEnd, timerPaused) {
	if (timerStart != 0) {
		// Set the time we're counting down to
		var countDownDate = timerEnd * 1000;
		// Get time now
		var now = new Date().getTime();
		
		// Find the distance between now and the count down time
		if(timerPaused == 0) {
			var distance = countDownDate - now;
		} else {
			var distance = countDownDate - ( timerPaused * 1000 );
		};
	} else {
		distance = 0;
	};

	return distance;
};

function timerPrettyTime(remainingSeconds) {
	var display = "";

	if (remainingSeconds < 0) {
		timerFinished();
		display = "Finished";
	} else if (remainingSeconds == 0) {
		display = "--:--:--";
	} else {
		// Time calculations for hours, minutes and seconds
		var hours = Math.floor((remainingSeconds % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
		var minutes = Math.floor((remainingSeconds % (1000 * 60 * 60)) / (1000 * 60));
		var seconds = Math.floor((remainingSeconds % (1000 * 60)) / 1000);
	
		if (hours < 10) {
			display += "0";
		}
		display += hours + " : ";
		if (minutes < 10) {
			display += "0"
		}
		display += minutes + " : ";
		if (seconds < 10) {
			display += "0"
		}
		display += seconds;
	};
	return display;
};

function timerUpdateTimeRemaining() {
	if (timerFinishedFlag != true) {
		var remainingSeconds= timerSecondsRemaining(timerEnd, timerPaused);
		var prettyTime = timerPrettyTime(remainingSeconds);
		$("#timer_time_remaining").html(prettyTime);
	};
};

function timerPause() {
	timerSuppressUpdate = true;
	timerButtonsPaused();
	req = $.ajax({
		url : '/api/set/timer/pause',
		type : 'POST',
	});
	req.done(function(response) {
		if (response.result == 'OK') {
			console.log('Timer paused.');
		} else {
			console.log('Error pausing timer: ' + response.message);
		};
	});
};

function timerUnPause() {
	timerSuppressUpdate = true;
	timerButtonsActive();
	req = $.ajax({
		url : '/api/set/timer/start',
		type : 'POST',
	});
	req.done(function(response) {
		if (response.result == 'OK') {
			console.log('Timer unpaused.');
		} else {
			console.log('Error unpausing timer: ' + response.message);
		};
	});
};

function timerStop() {
	timerSuppressUpdate = true;
	timerButtonsInactive();
	req = $.ajax({
		url : '/api/set/timer/stop',
		type : 'POST',
	});
	req.done(function(response) {
		if (response.result == 'OK') {
			console.log('Timer stopped.');
			document.getElementById("timerButton").className = "btn btn-outline-secondary border-secondary";
		} else {
			console.log('Error stopping timer: ' + response.message);
		};
	});
};

function timerStatus() {
    // Get Current Timer Data
    req = $.ajax({
        url : '/api/get/timer',
        type : 'GET'
    });

    req.done(function(response) {
		if (response.data.start != timerStart) {
			// Timer has likely been updated elsewhere
			timerFinishedFlag = false;  // Clear finished flag to allow the timer to start updating again
			timerUserHidden = false; // Clear the user hidden flag, in case the user had previously hidden the timer
			// Show the Timer
			$("#timer_bar").slideDown();
			$("#toggleTimer").html('unhidden');
			//document.getElementById("timerButton").className = "btn btn-outline-secondary border-warning text-warning";
		};
		timerStart = response.data.start;
		timerPaused = response.data.paused;
		timerEnd = response.data.end;
		timerShutdown = response.data.shutdown;
		timerKeepWarm = response.data.keep_warm;

		if(timerEnd != 0) {
			secondsRemaining = timerSecondsRemaining(timerEnd, timerPaused);
	
			// If the count down is finished, end updates, and display finished 
			if (secondsRemaining < 0) {
				timerFinished();
			}
		}
	});
};

function timerFinished() {
	timerFinishedFlag = true;
	timerSuppressUpdate = true;
	timerStart = 0;
	timerButtonsInactive();
	console.log('Timer Expired.');
	$("#timer_time_remaining").html("Finished");
	document.getElementById("timerButton").className = "btn btn-outline-secondary border-secondary";
};

// Depending on state, show the correct button set
function timerShowButtons() {
	if(timerFinishedFlag == true) {
		timerButtonsInactive();
	} else if(timerStart != 0) {
		// Timer is active, so let's set things up
		if(timerPaused != 0) {
			// Timer is paused
			timerButtonsPaused();
		} else {
			// Timer is active
			timerButtonsActive();
		}
	} else {
		// Timer is inactive 
		timerButtonsInactive();
	};
};

function timerButtonsActive() {
	// Timer is running
	$("#timerStartGroup").hide();
	$("#timerPausedGroup").hide();
	$("#timerActiveGroup").show();
	document.getElementById("timerButton").className = "btn btn-outline-secondary border-warning text-warning";
};

function timerButtonsInactive() {
	// Timer is inactive 
	$("#timerActiveGroup").hide();
	$("#timerPausedGroup").hide();
	$("#timerStartGroup").show();
};

function timerButtonsPaused() {
	// Timer is paused 
	$("#timerActiveGroup").hide();
	$("#timerStartGroup").hide();
	$("#timerPausedGroup").show();
};

// Launch a timer 
function timerLaunch() {
	timerButtonsActive();
	timerFinishedFlag = false;
	timerSuppressUpdate = true;

	clearTimeout(timerUpdateTimerStatus);
	timerUpdateTimerStatus = setTimeout(timerRefresh, 1000);  // When timer is active, refresh faster 

	var timerHours = $("#hoursInputId").val();
	var timerMins = $("#minsInputId").val();
	var timerSeconds = (timerHours * 3600) + (timerMins * 60);

	if ($('#shutdownTimer').is(":checked")){
		timerShutdown = true;
	};
	if ($('#keepWarmTimer').is(":checked")){
		timerKeepWarm = true;
	};

	req = $.ajax({
		url : '/api/set/timer/start/'+timerSeconds,
		type : 'POST',
		data : {}
	});
	req.done(function(response) {
		if (response.result == 'OK') {
			console.log('Timer Launched Successfully: ' + response.message);
		} else {
			console.log('Error launching timer: ' + response.message);
		};
	});
};

// Prevent both KeepWarm and Shutdown to be selected at the same time
function timerShutdownSelect() {
	if ($('#keepWarmTimer').is(":checked")){
		$('#keepWarmTimer').prop('checked', false);
	};
};

// Prevent both KeepWarm and Shutdown to be selected at the same time
function timerKeepWarmSelect() {
	if ($('#shutdownTimer').is(":checked")){
		$('#shutdownTimer').prop('checked', false);
	};
};

function timerRefresh() {
	timerStatus();
	if (timerSuppressUpdate == false) {
		timerShowButtons();
	};
	timerSuppressUpdate = false;
	//console.log('Refreshed: ' + new Date().getTime());
	if (timerStart != 0) {
		clearTimeout(timerUpdateTimerStatus);
		timerUpdateTimerStatus = setTimeout(timerRefresh, 1000);  // When timer is active, refresh faster 
	} else {
		clearTimeout(timerUpdateTimerStatus);
		timerUpdateTimerStatus = setTimeout(timerRefresh, 5000);  // When timer is inactive, refresh slower
	};
};

// On document ready
$(document).ready(function(){
	timerUpdateTimerStatus = setTimeout(timerRefresh, 100);  // Start the timeout for refreshing the timer status, drawing buttons, etc. 
	timerUpdateTimerValue = setInterval(timerUpdateTimeRemaining, 250);  // Start the interval for updating the displayed timer value
});


