
var finished = false;

// Functions
function scrollTop() {
	window.scroll({
 		top: 0,
 		left: 0,
 		behavior: 'smooth'
	});
}

// On Document Ready
$(document).ready(function() {
	$("#platformBtn").click(function() {
		$("#v-pills-platform-tab").trigger('click');
		scrollTop()
	});
	$("#platformBack").click(function() {
		$("#v-pills-start-tab").trigger('click');
		scrollTop()
	});
	$("#probesBtn").click(function() {
		$("#v-pills-probes-tab").trigger('click');
		scrollTop()
	});
	$("#probesBack").click(function() {
		$("#v-pills-platform-tab").trigger('click');
		scrollTop()
	});
	$("#displayBtn").click(function() {
		$("#v-pills-display-tab").trigger('click');
		scrollTop()
	});
	$("#displayBack").click(function() {
		$("#v-pills-probes-tab").trigger('click');
		scrollTop()
	});
	$("#distanceBtn").click(function() {
		$("#v-pills-distance-tab").trigger('click');
		scrollTop()
	});
	$("#distanceBack").click(function() {
		$("#v-pills-display-tab").trigger('click');
		scrollTop()
	});
	$("#finishtabBtn").click(function() {
		$("#v-pills-finish-tab").trigger('click');
		scrollTop()
	});
	$("#finishtabBack").click(function() {
		$("#v-pills-distance-tab").trigger('click');
		scrollTop()
	});
	$("#finishBtn").click(function() {
		finished = true;
		$('#wizardForm').submit();
	});

	// Function for Calling Card Info
	var selection = $('#grillplatformSelect').val();
	$('#grillplatformCard').load("/wizard/modulecard", {"section" : "grillplatform", "module" : selection});
	$('#grillplatformConfirm').html(selection);

	var selection = $('#probesSelect').val();
	$('#probesCard').load("/wizard/modulecard", {"section" : "probes", "module" : selection});
	$('#probesConfirm').html(selection);

	var selection = $('#displaySelect').val();
	$('#displayCard').load("/wizard/modulecard", {"section" : "display", "module" : selection});
	$('#displayConfirm').html(selection);

	var selection = $('#distanceSelect').val();
	$('#distanceCard').load("/wizard/modulecard", {"section" : "distance", "module" : selection});
	$('#distanceConfirm').html(selection);

	// Setup listeners for selection boxes
	$('#grillplatformSelect').change(function () {
		var selection = $('#grillplatformSelect').val();
		$('#grillplatformCard').load("/wizard/modulecard", {"section" : "grillplatform", "module" : selection});
		$('#grillplatformConfirm').html(selection);
	});
	$('#probesSelect').change(function () {
		var selection = $('#probesSelect').val();
		$('#probesCard').load("/wizard/modulecard", {"section" : "probes", "module" : selection});
		$('#probesConfirm').html(selection);
	});
	$('#displaySelect').change(function () {
		var selection = $('#displaySelect').val();
		$('#displayCard').load("/wizard/modulecard", {"section" : "display", "module" : selection});
		$('#displayConfirm').html(selection);
	});
	$('#distanceSelect').change(function () {
		var selection = $('#distanceSelect').val();
		$('#distanceCard').load("/wizard/modulecard", {"section" : "distance", "module" : selection});
		$('#distanceConfirm').html(selection);
	});

});