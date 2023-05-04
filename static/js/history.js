// Global Variables 
var lastCookMode = 'PageLoad';
var chartReady = false;
var annotation_enabled = true;
var paused = false;
var probe_mapper = {};
var ui_hash;

Chart.defaults.font.family = '"Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", "Liberation Sans"';

var chartdata = {
	labels: [],
	datasets: [],
};

var temperatureCharts = new Chart(document.getElementById('HistoryChart'), {
	type: 'line',
	data: chartdata,
	options: {
		plugins: {
			legend: {
				labels: {
					usePointStyle: false,
				}
			}, 
			annotation: {
				annotations: {}
			},
			streaming: {
				frameRate: 5   // chart is drawn 5 times every second
			}
		},
		scales: {
			x: {
				type: 'realtime',
				realtime: {
					duration: duration_window, 
					delay: 2000,
					refresh: 1000,
					pause: paused,
					onRefresh: chart => {
						$.get("/historyupdate/stream", function(data){
							checkHashChange(data.ui_hash); 
							checkModeChange(data.mode);
							if (chartReady) {
								var dateNow = Date.now();
								// append the new label (time) to the label list
								chart.data.labels.push(dateNow);
								// append the new data array to the existing chart data
								//chart.data.datasets[0].data.push(data.probe0_temp);
								for (probe in data.current.P) {
									chart.data.datasets[probe_mapper['probes'][probe]].data.push(data.current.P[probe]);
									chart.data.datasets[probe_mapper['primarysp'][probe]].data.push(data.current.PSP);
								};
								for (probe in data.current.F) {
									chart.data.datasets[probe_mapper['probes'][probe]].data.push(data.current.F[probe]);
								};
								for (probe in data.current.NT) {
									chart.data.datasets[probe_mapper['targets'][probe]].data.push(data.current.NT[probe]);
								};

								if (annotation_enabled == true) {
									chart.options.plugins.annotation.annotations = data.annotations;
								} else {
									chart.options.plugins.annotation.annotations = {};
								};
							};
						});
					}
				}
			  },
			y: {
				ticks: {}, 
				beginAtZero:true
			}
		},
		responsive: true,
		maintainAspectRatio: false,
		animation: false
	}
});

// Delete Cook File Modal Data Transfer
$('#delcookfilemodal').on('show.bs.modal', function (event) {
	var cookfileselected = $(event.relatedTarget).data('val');
	 $('#cookfileselected').html(cookfileselected);
   $('#delcookfilename').val(cookfileselected);
   });

// Goto page in pagination of cookfiles
function gotoCFPage(pagenum, sortorder, itemsperpage) {
	// Load updated paginated data
	var senddata = { 
		'cookfilelist' : true,
		'page' : pagenum, 
		'reverse' : sortorder, 
		'itemsperpage' : itemsperpage
	};
	$('#cookfilelist').load('/cookfiledata', senddata)
};

function checkModeChange(mode) {
	if (((mode == 'Stop') || (mode == 'Error')) && (mode != lastCookMode)) {
		$('#graphcardbody').hide();
		$('#graphcardfooter').hide();
		$('#stopcardbody').show();
		if (lastCookMode != 'PageLoad') {
			// refresh cook file listing after 1 second 
			var refreshCFList = setInterval(function(){
				gotoCFPage(1, true, 10);
				clearInterval(refreshCFList);
			}, 1000); 
		};
		lastCookMode = mode;
		temperatureCharts.options.scales.x.realtime.pause = true;
		paused = true;
		chartReady = false;
	} else if (mode != lastCookMode) {
		$('#stopcardbody').hide();
		$('#graphcardbody').show();
		$('#graphcardfooter').show();
		if ((['PageLoad', 'Error'].includes(lastCookMode)) || (chartReady == false)) {
			refreshChartData();
		}; 
		lastCookMode = mode;
		checkAutorefresh();
	};
};

// Check UI Hash to see if there was a server change
function checkHashChange(cur_hash) {
	if (lastCookMode == 'PageLoad') {
		ui_hash = cur_hash;
	} else if (cur_hash != ui_hash) {
		$("#serverReloadModal").modal('show');
	};
};

// Get initial chart 
function refreshChartData() {
	var newDuration = $("#minutes").val();
	var postdata = { 
		'num_mins' : newDuration
	};
	req = $.ajax({
		url : '/historyupdate/refresh',
		type : 'POST',
		data : JSON.stringify(postdata),
		contentType: "application/json; charset=utf-8",
		traditional: true,
		success: function (data) {
			// Update duration scale (convert up to milliseconds)
			temperatureCharts.options.scales.x.realtime.duration = newDuration * 60 * 1000;
			// Update time label list
			temperatureCharts.data.labels = data.time_labels;
			// Update chart datasets
			temperatureCharts.data.datasets = data.chart_data;
			// Update annotations 
			temperatureCharts.options.plugins.annotation.annotations = data.annotations;
			// Update Chart
			temperatureCharts.update();
			// Update probe mapper object 
			probe_mapper = data.probe_mapper;
			// Set Chart Ready Flag
			chartReady = true;
		}
	});
};

function checkAutorefresh() {
	if ($("#autorefresh").val() == 'on') {
		temperatureCharts.options.scales.x.realtime.pause = true;
		document.getElementById("autorefresh").className = "btn btn-secondary text-white";
		document.getElementById("autorefresh").innerHTML = "<i class=\"fas fa-sync-alt\"></i>&nbsp;Stream OFF";
		paused = true;
	} else {
		temperatureCharts.options.scales.x.realtime.pause = false;
		document.getElementById("autorefresh").className = "btn btn-outline-primary";
		document.getElementById("autorefresh").innerHTML = "<i class=\"fas fa-sync-alt\"></i>&nbsp;Stream ON";
		paused = false;
	};

};

$("#autorefresh").click(function() {
	if ($("#autorefresh").val() == 'off') {
		$("#autorefresh").val('on');
	} else {
		$("#autorefresh").val('off');
	};
	checkAutorefresh();
});

// Changing the duration window with the slider
$("#durationWindowInput").change(function() {
	refreshChartData();
});

// If a reload is required due to a server change, reload page
$('#reloadPage').click(function() {
	// Reload page when server side changes detected. 
	location.reload(); 
});


$("#annotation_enabled").change(function() {
		
	if(document.getElementById('annotation_enabled').checked) {
		annotation_enabled = true;
	} else {
		annotation_enabled = false;
	};

	// If streaming is paused, update chart manually
	if(paused == true) {
		if (annotation_enabled == true) {
			$.get("/historyupdate/stream", function(data) {
				temperatureCharts.options.plugins.annotation.annotations = data.annotations;
			});
		} else {
			temperatureCharts.options.plugins.annotation.annotations = {};
		};			
		// Update Chart
		temperatureCharts.update();
	};
});

$(document).ready(function(){
	// Load the paginated cookfile list
	gotoCFPage(1, true, 10);
	checkAutorefresh();
}); // End of Document Ready Function 
