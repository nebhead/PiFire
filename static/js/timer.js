// Timer Bar JS
// Puts timer status in the top-bar

function countdown(timerEnd, timerPaused) {
	// Set the date we're counting down to
	var countDownDate = timerEnd * 1000;

	// Get today's date and time
	var now = new Date().getTime();
    
	// Find the distance between now and the count down date
	if(timerPaused == 0) {
		var distance = countDownDate - now;
	} else {
		var distance = countDownDate - ( timerPaused * 1000 );
	};

	// Time calculations for days, hours, minutes and seconds
	var days = Math.floor(distance / (1000 * 60 * 60 * 24));
	var hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
	var minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
	var seconds = Math.floor((distance % (1000 * 60)) / 1000);

	var display = "";
	// Display the result in the element with id="demo"
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

	$("#timer_time_remaining").html(display);

	return distance
};

function timerSetup() {
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
			timerSetup();
		}
	});
});
