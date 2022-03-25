$(document).ready(function(){
	var chartdata = {
			labels: label_list,
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
							data: grill_temp_list,
							spanGaps: false,
					},
					{
							label: "Grill Set Point",
							fill: false,
							lineTension: 0.1,
							backgroundColor: "rgba(0,0,255,0.4)",
							borderColor: "rgba(0,0,255,1)",
							borderCapStyle: 'butt',
							borderDash: [],
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
							data: grill_settemp_list,
							spanGaps: false,
							hidden: probe0_hidden,
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
							data: probe1_temp_list,
							spanGaps: false,
							hidden: probe1_hidden,
					},
					{
							label: "Probe-1 Set Point",
							fill: false,
							lineTension: 0.1,
							backgroundColor: "rgba(127,0,0,0.4)",
							borderColor: "rgba(127,0,0,1)",
							borderCapStyle: 'butt',
							borderDash: [],
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
							data: probe1_settemp_list,
							spanGaps: false,
							hidden: probe1_hidden,
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
							data: probe2_temp_list,
							spanGaps: false,
							hidden: probe2_hidden,
					},
					{
							label: "Probe-2 Set Point",
							fill: false,
							lineTension: 0.1,
							backgroundColor: "rgba(0,255,0,0.4)",
							borderColor: "rgba(0,255,0,1)",
							borderCapStyle: 'butt',
							borderDash: [],
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
							data: probe2_settemp_list,
							spanGaps: false,
							hidden: probe2_hidden,
					}
			]
		}

	var temperatureCharts = new Chart(document.getElementById('HistoryChart'), {
			type: 'line',
			data: chartdata,
			options: {
				scales: {
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

	function getNewData() {
		// Get Data from historyupdate route
		req = $.ajax({
			url : '/historyupdate',
			type : 'GET'
		});
	
		req.done(function(data) {
			// Update chart data
			// console.log(data);  // Debug logging
	
			// Returned Lists: 
			// 'grill_temp_list' 
			// 'grill_settemp_list'
			// 'probe1_temp_list' 
			// 'probe1_settemp_list'
			// 'probe2_temp_list' 
			// 'probe2_settemp_list' 
			// 'label_time_list' 
	
			// Replace data for each dataset and label list
			temperatureCharts.data.labels = data.label_time_list;
			temperatureCharts.data.datasets[0].data = data.grill_temp_list;
			temperatureCharts.data.datasets[1].data = data.grill_settemp_list;
			temperatureCharts.data.datasets[2].data = data.probe1_temp_list;
			temperatureCharts.data.datasets[3].data = data.probe1_settemp_list;
			temperatureCharts.data.datasets[4].data = data.probe2_temp_list;
			temperatureCharts.data.datasets[5].data = data.probe2_settemp_list;
			
			// Update Chart
			temperatureCharts.update();
		});
	};

	var refreshfunc;

	if ($("#autorefresh").val() == 'off') {
		refreshfunc = setInterval(getNewData, 1000); // Update chart every 1 second
	};

	$("#autorefresh").click(function() {
		if ($("#autorefresh").val() == 'off') {
			$("#autorefresh").val('on');
			clearInterval(refreshfunc);
			document.getElementById("autorefresh").className = "btn btn-secondary text-light float-right";
			document.getElementById("autorefresh").innerHTML = "<i class=\"fas fa-sync-alt\"></i> OFF";
		} else {
			$("#autorefresh").val('off');
			refreshfunc = setInterval(getNewData, 1000); // Update chart every 1 second
			document.getElementById("autorefresh").className = "btn btn-outline-primary border-white text-white float-right";
			document.getElementById("autorefresh").innerHTML = "<i class=\"fas fa-sync-alt\"></i> ON";
		};

	});

}); // End of Document Ready Function 