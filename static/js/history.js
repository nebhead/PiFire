// Convert labels (timestamps) to integers
var label_list_num = label_list.map(Number);

// Calculate initial display window
var duration_window = 1000 * 60 * display_mins;

// Check if there is any set-temp history and hide set-temp if none
var grill_settemp_hidden = false;
if ((grill_settemp_list.reduce((a, b) => a + b, 0) == 0) || (probe0_hidden == true)) {
	//console.log('Hiding Grill Set Temp')
	grill_settemp_hidden = true;
}

var probe1_settemp_hidden = false;
if ((probe1_settemp_list.reduce((a, b) => a + b, 0) == 0) || (probe1_hidden == true)) {
	//console.log('Hiding Probe1 Set Temp')
	probe1_settemp_hidden = true;
}

var probe2_settemp_hidden = false;
if ((probe2_settemp_list.reduce((a, b) => a + b, 0) == 0) || (probe2_hidden == true)) {
	//console.log('Hiding Probe2 Set Temp')
	probe2_settemp_hidden = true;
}

var temperatureCharts;
var chartdata;

$(document).ready(function(){
	chartdata = {
		labels: label_list_num,
		datasets: [
			{
				label: "Grill Temp",
				fill: false,
				lineTension: 0.1,
				backgroundColor: "rgba(0,0,127,0.4)",
				borderColor: "rgba(0,0,127,1)",
				borderCapStyle: 'butt',
				borderDash: [],
				borderDashOffset: 0.0,
				borderJoinStyle: 'miter',
				pointBorderColor: "rgba(0,0,127,1)",
				pointBackgroundColor: "#fff",
				pointBorderWidth: 1,
				pointHoverRadius: 5,
				pointHoverBackgroundColor: "rgba(0,0,127,0.4)",
				pointHoverBorderColor: "rgba(0,0,127,1)",
				pointHoverBorderWidth: 2,
				pointRadius: 1,
				pointHitRadius: 10,
				pointStyle: 'line',
				data: grill_temp_list,
				spanGaps: false,
				hidden: probe0_hidden,
			},
			{
				label: "Grill Set Point",
				fill: false,
				lineTension: 0,
				backgroundColor: "rgba(0,0,255,0.4)",
				borderColor: "rgba(0,0,255,1)",
				borderCapStyle: 'butt',
				borderDash: [8,4],
				borderDashOffset: 0.0,
				borderJoinStyle: 'miter',
				pointBorderColor: "rgba(0,0,255,1)",
				pointBackgroundColor: "#fff",
				pointBorderWidth: 1,
				pointHoverRadius: 5,
				pointHoverBackgroundColor: "rgba(0,0,255,0.4)",
				pointHoverBorderColor: "rgba(0,0,255,1)",
				pointHoverBorderWidth: 2,
				pointRadius: 1,
				pointHitRadius: 10,
				pointStyle: 'dash',
				data: grill_settemp_list,
				spanGaps: false,
				hidden: grill_settemp_hidden,
			},
			{
				label: "Probe-1 Temp",
				fill: false,
				lineTension: 0.1,
				backgroundColor: "rgba(256,0,0,0.4)",
				borderColor: "rgba(256,0,0,1)",
				borderCapStyle: 'butt',
				borderDash: [],
				borderDashOffset: 0.0,
				borderJoinStyle: 'miter',
				pointBorderColor: "rgba(256,0,0,1)",
				pointBackgroundColor: "#fff",
				pointBorderWidth: 1,
				pointHoverRadius: 5,
				pointHoverBackgroundColor: "rgba(256,0,0,0.4)",
				pointHoverBorderColor: "rgba(256,0,0,1)",
				pointHoverBorderWidth: 2,
				pointRadius: 1,
				pointHitRadius: 10,
				pointStyle: 'line',
				data: probe1_temp_list,
				spanGaps: false,
				hidden: probe1_hidden,
			},
			{
				label: "Probe-1 Set Point",
				fill: false,
				lineTension: 0,
				backgroundColor: "rgba(127,0,0,0.4)",
				borderColor: "rgba(127,0,0,1)",
				borderCapStyle: 'butt',
				borderDash: [8,4],
				borderDashOffset: 0.0,
				borderJoinStyle: 'miter',
				pointBorderColor: "rgba(127,0,0,1)",
				pointBackgroundColor: "#fff",
				pointBorderWidth: 1,
				pointHoverRadius: 5,
				pointHoverBackgroundColor: "rgba(127,0,0,0.4)",
				pointHoverBorderColor: "rgba(127,0,0,1)",
				pointHoverBorderWidth: 2,
				pointRadius: 1,
				pointHitRadius: 10,
				pointStyle: 'dash',
				data: probe1_settemp_list,
				spanGaps: false,
				hidden: probe1_settemp_hidden,
			},
			{
				label: "Probe-2 Temp",
				fill: false,
				lineTension: 0.1,
				backgroundColor: "rgba(0,127,0,0.4)",
				borderColor: "rgba(0,127,0,1)",
				borderCapStyle: 'butt',
				borderDash: [],
				borderDashOffset: 0.0,
				borderJoinStyle: 'miter',
				pointBorderColor: "rgba(0,127,0,1)",
				pointBackgroundColor: "#fff",
				pointBorderWidth: 1,
				pointHoverRadius: 5,
				pointHoverBackgroundColor: "rgba(0,127,0,0.4)",
				pointHoverBorderColor: "rgba(0,127,0,1)",
				pointHoverBorderWidth: 2,
				pointRadius: 1,
				pointHitRadius: 10,
				pointStyle: 'line',
				data: probe2_temp_list,
				spanGaps: false,
				hidden: probe2_hidden,
			},
			{
				label: "Probe-2 Set Point",
				fill: false,
				lineTension: 0,
				backgroundColor: "rgba(0,255,0,0.4)",
				borderColor: "rgba(0,255,0,1)",
				borderCapStyle: 'butt',
				borderDash: [8,4],
				borderDashOffset: 0.0,
				borderJoinStyle: 'miter',
				pointBorderColor: "rgba(0,255,0,1)",
				pointBackgroundColor: "#fff",
				pointBorderWidth: 1,
				pointHoverRadius: 5,
				pointHoverBackgroundColor: "rgba(0,255,0,0.4)",
				pointHoverBorderColor: "rgba(0,255,0,1)",
				pointHoverBorderWidth: 2,
				pointRadius: 1,
				pointHitRadius: 10,
				pointStyle: 'dash',
				data: probe2_settemp_list,
				spanGaps: false,
				hidden: probe2_settemp_hidden,
			}
		]
	}

	temperatureCharts = new Chart(document.getElementById('HistoryChart'), {
			type: 'line',
			data: chartdata,
			options: {
				plugins: {
					legend: {
						labels: {
							usePointStyle: true,
						}
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
									// Reverse logic for auto-refresh button
									if ($("#autorefresh").val() == 'on') {
										var paused = true;
										temperatureCharts.options.scales.x.realtime.pause = true;
										document.getElementById("autorefresh").className = "btn btn-secondary text-light float-right";
										document.getElementById("autorefresh").innerHTML = "<i class=\"fas fa-sync-alt\"></i> OFF";
										return;
									}
									var dateNow = Date.now();
									// append the new label (time) to the label list
									chart.data.labels.push(dateNow);
									// append the new data array to the existing chart data
									chart.data.datasets[0].data.push(data.probe0_temp);
									chart.data.datasets[1].data.push(data.probe0_settemp);
									chart.data.datasets[2].data.push(data.probe1_temp);
									chart.data.datasets[3].data.push(data.probe1_settemp);
									chart.data.datasets[4].data.push(data.probe2_temp);
									chart.data.datasets[5].data.push(data.probe2_settemp);
									// unhide set temps if they are turned on AND the probes aren't hidden globally
									if ((data.probe0_settemp > 0) && (chart.data.datasets[1].hidden == true) && (chart.data.datasets[0].hidden == false)) {
										chart.data.datasets[1].hidden = false;
									};
									if ((data.probe1_settemp > 0) && (chart.data.datasets[3].hidden == true) && (chart.data.datasets[2].hidden == false)) {
										chart.data.datasets[3].hidden = false;
									};
									if ((data.probe2_settemp > 0) && (chart.data.datasets[5].hidden == true) && (chart.data.datasets[4].hidden == false)) {
										chart.data.datasets[5].hidden = false;
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

	$("#autorefresh").click(function() {
		if ($("#autorefresh").val() == 'off') {
			$("#autorefresh").val('on');
			temperatureCharts.options.scales.x.realtime.pause = true;
			document.getElementById("autorefresh").className = "btn btn-secondary text-light float-right";
			document.getElementById("autorefresh").innerHTML = "<i class=\"fas fa-sync-alt\"></i> OFF";
		} else {
			$("#autorefresh").val('off');
			temperatureCharts.options.scales.x.realtime.pause = false;
			document.getElementById("autorefresh").className = "btn btn-outline-primary border-white text-white float-right";
			document.getElementById("autorefresh").innerHTML = "<i class=\"fas fa-sync-alt\"></i> ON";
		};

	});

	// Changing the duration window with the slider
	$("#durationWindowInput").change(function() {
		var newDuration = $("#minutes").val();
		//console.log(newDuration);
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
                //console.log('Updating Data');
				// Update duration scale
				temperatureCharts.options.scales.x.realtime.duration = newDuration * 60 * 1000;
				// Replace data for each dataset and label list
				temperatureCharts.data.labels = data.label_time_list;
				//console.log(data.label_time_list);
				temperatureCharts.data.datasets[0].data = data.grill_temp_list;
				temperatureCharts.data.datasets[1].data = data.grill_settemp_list;
				temperatureCharts.data.datasets[2].data = data.probe1_temp_list;
				temperatureCharts.data.datasets[3].data = data.probe1_settemp_list;
				temperatureCharts.data.datasets[4].data = data.probe2_temp_list;
				temperatureCharts.data.datasets[5].data = data.probe2_settemp_list;
				
				// Update Chart
				temperatureCharts.update();
            }
		});

		
	});

}); // End of Document Ready Function 

