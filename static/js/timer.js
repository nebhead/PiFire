// Timer Bar JS
// Puts timer status in the top-bar
function timerToggle() {
	if ($("#toggleTimer").html() == 'hidden') {
		$("#timer_bar").slideDown();
		$("#toggleTimer").html('unhidden');
	} else {
		$("#timer_bar").slideUp();
		$("#toggleTimer").html('hidden');
	};
};

function countdown(timerEnd, timerPaused) {
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

	// Time calculations for hours, minutes and seconds
	var hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
	var minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
	var seconds = Math.floor((distance % (1000 * 60)) / 1000);

	var display = "";

	if ((hours < 0) || (minutes < 0) || (seconds < 0)) {
		display = "--:--:--";
	} else {
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

	$("#timer_time_remaining").html(display);

	return distance
};

function timerSetup() {
	// Turn Timer Button in Navbar Yellow 
	document.getElementById("timerButton").className = "btn btn-outline-warning border-secondary";
	// Setup Button Listeners
	$("#timer_start").click(function(){
		req = $.ajax({
			url : '/timer',
			type : 'POST',
			data : { 'input' : 'timer_start' }
		});
		req.done(function(data) { 
			$("#timer_pause").show();
			$("#timer_start").hide();
		});
	});

	$("#timer_pause").click(function(){
		req = $.ajax({
			url : '/timer',
			type : 'POST',
			data : { 'input' : 'timer_pause' }
		});
		req.done(function(data) { 
			$("#timer_pause").hide();
			$("#timer_start").show();
		});
	});

	$("#timer_stop").click(function(){
		req = $.ajax({
			url : '/timer',
			type : 'POST',
			data : { 'input' : 'timer_stop' }
		});
		req.done(function(data) { 
			clearInterval(timerInterval);
			$("#timer_btn_grp").html("<button type=\"button\" class=\"btn btn-warning\"><i class=\"fas fa-stopwatch\"></i>&nbsp; <i>Stopped</i></button>");
			document.getElementById("timerButton").className = "btn btn-outline-secondary border-secondary";
		});
	});

	$("#timer_hide").click(function(){
		clearInterval(timerInterval);
		$("#timer_bar").slideUp();
	});


	// Init Variables 
	var timerEnd = 0;
	var timerPaused = 0;

	// Update the count down every 1 second
	var timerInterval = setInterval(function() {
		
		if(timerEnd != 0) {
			distance = countdown(timerEnd, timerPaused);
	
			// If the count down is finished, end updates, and display finished 
			if (distance < 0) {
				clearInterval(timerInterval);
				$("#timer_btn_grp").html("<button type=\"button\" class=\"btn btn-warning\"><i class=\"fas fa-stopwatch\"></i>&nbsp; <i>Finished</i></button>");
				document.getElementById("timerButton").className = "btn btn-outline-secondary border-secondary";
			}
		}
		// Get Current Timer Data
		req = $.ajax({
			url : '/timer',
			type : 'GET'
		});

		req.fail(function(xhr, error) {
			//Ajax request failed, ignore and keep clock running.
		});

		req.done(function(data) {
			if((data.paused != timerPaused) && (data.paused != 0)) {
				// Timer is paused
				timerPaused = data.paused;
				timerEnd = data.end; 
				distance = countdown(timerEnd, timerPaused);
				$("#timer_pause").hide();
				$("#timer_start").show();
			} else if((data.paused != timerPaused) && (data.paused == 0)) {
				// Timer is unpaused
				timerPaused = data.paused;
				timerEnd = data.end; 
				distance = countdown(timerEnd, timerPaused);
				$("#timer_pause").show();
				$("#timer_start").hide();
			} else if(data.end != timerEnd) {
				// Timer has new end time / so update
				timerEnd = data.end;
				distance = countdown(timerEnd, timerPaused); 
				$("#timer_pause").show();
				$("#timer_start").hide();
			}
		});
	}, 1000);
};

$(document).ready(function(){
    // Get Intial Timer Data
    req = $.ajax({
        url : '/timer',
        type : 'GET'
    });

    req.done(function(data) {
		if(data.start != 0) {
			// Timer is active, so let's set things up
			if(data.paused != 0) {
				// Timer is paused
				$("#timer_pause").hide();
			} else {
				// Timer is running
				$("#timer_start").hide();
			}
			// Show the Timer
			$("#timer_bar").slideDown();
			$("#toggleTimer").html('unhidden');
			timerSetup();
		}
	});
});

// Launch a timer 
$("#timer_launch").click(function(){
	var timerHours = $("#hoursInputId").val();
	var timerMins = $("#minsInputId").val();
	var timerShutdown = false;
	var timerKeepWarm = false;
	if ($('#shutdownTimer').is(":checked")){
		timerShutdown = true;
	}
	if ($('#keepWarmTimer').is(":checked")){
		timerKeepWarm = true;
	}
	// For Debug
	//console.log("Hours: " + timerHours);
	//console.log("Mins: " + timerMins);
	//console.log("Shutdown: " + timerShutdown);
	req = $.ajax({
		url : '/timer',
		type : 'POST',
		data : { 'input' : 'timer_start',  
				'hoursInputRange' : timerHours,
				'minsInputRange' : timerMins, 
				'shutdownTimer' : timerShutdown,
				'keepWarmTimer' : timerKeepWarm
		}
	});
	req.done(function(data) {
		$("#timer_bar").slideUp();
		$("#timer_btn_grp").html("\
			<button type=\"button\" class=\"btn btn-warning\"><i class=\"fas fa-stopwatch\"></i>&nbsp; <i id=\"timer_time_remaining\">--:--:--</i></button>\
			<button type=\"button\" data-toggle=\"tooltip\" title=\"Start the timer\" class=\"btn btn-outline-success border-warning\" id=\"timer_start\"><i class=\"fas fa-play-circle\"></i></button>\
			<button type=\"button\" data-toggle=\"tooltip\" title=\"Pause the timer\" class=\"btn btn-outline-warning\" id=\"timer_pause\"><i class=\"fas fa-pause-circle\"></i></button>\
			<button type=\"button\" data-toggle=\"tooltip\" title=\"Stop the timer\" class=\"btn btn-outline-danger border-warning\" id=\"timer_stop\"><i class=\"fas fa-stop-circle\"></i></button>\
		");
		$("#timer_pause").hide();
		$("#timer_start").hide();
		$("#timer_bar").slideDown();
		$("#timerButton")
		timerSetup();
	});
});