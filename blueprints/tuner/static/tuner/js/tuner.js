// === Global Variables ===
var tunerProbeSelected = 'none';
var tunerProbeSelectedName = 'none';
var tunerProbeReference = 'none';
var tunerProbeReferenceName = 'none';
var tunerFetchTrValues;
var tunerAutoStatus;

// In Manual Tuning, Pause updating Tr value when requested
var tunerManualHighPaused = false;
var tunerManualMediumPaused = false;
var tunerManualLowPaused = false;

var tunerManualHighTr = 0;
var tunerManualHighTemp = 0;
var tunerManualMediumTr = 0;
var tunerManualMediumTemp = 0;
var tunerManualLowTr = 0;
var tunerManualLowTemp = 0;

var tunerRunning = false;
var _wasPageCleanedUp = false;

// Chart Data
var tunerChartData = {
    labels: [],
    datasets: [
            {
                    label: "Stienhart-Hart Curve",
                    fill: true,
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
                    data: [],
                    spanGaps: false,
            },
    ]
}

var tunerResultsChart = new Chart(document.getElementById('tunerResultsChart'), {
    type: 'line',
    data: tunerChartData,
    options: {
        scales: {
            x: {
                title: {
                    display: true,
                    text: 'Temperature'
                },
            },
            y: {
                title: {
                    display: true,
                    text: 'Resistance (Ohms)',
                    ticks: {}, 
				    beginAtZero:true
                },
            }
        },
        responsive: true,
        maintainAspectRatio: false,
    }
});

// === Function Definitions ===
function tunerCheckState() {
    // Call API to check state of system 
};

// === MANUAL Tuner Functions ===
function tunerManualInstructions() {
    // User Selected Manual Tuning Mode 
    // Hide Welcome Row & Show Manual Tuning Instructions 
    $("#tuner_welcome_row").hide();
    $("#tuner_back_to_welcome_row").show();
    var senddata = {
		'command' : 'render',
		'value' : 'manual_instruction_card',
	};
	$('#tuner_instruction_row').load('/tuner', senddata);
    $('#tuner_instruction_row').show();
};

function tunerEnableManualStart(sel) {
    tunerProbeSelected = sel.value;
    tunerProbeSelectedName = sel.options[sel.selectedIndex].text;

    // Start button is disabled until the user selects a probe to tune 
    if (tunerProbeSelected != 'none') {
        $("#tuner_manual_start_btn").prop('disabled', false);
    } else {
        $("#tuner_manual_start_btn").prop('disabled', true);
    };
};

function tunerStartManualTool() {
    tunerRunning = true;
    // Hide the instructions and start the Manual Tool
    $("#tuner_instruction_row").hide();
    $("#tuner_back_to_welcome_row").show();

    $('#tuner_manual_tool_title_probe_selected').html(tunerProbeSelectedName);
    $("#tuner_tool_manual_title_row").show();

    var senddata = {
		'command' : 'render',
		'value' : 'manual_tool',
	};
	$('#tuner_tool_row').load('/tuner', senddata);
    $("#tuner_tool_row").show();

    var senddata = {
		'command' : 'render',
		'value' : 'manual_finish_btn',
	};
	$('#tuner_finish_btn_row').load('/tuner', senddata);
    $("#tuner_finish_btn_row").show();

    tunerFetchTrValues = setInterval(tunerUpdateTr,1000);
};

function tunerManualPause(segment) {
    //console.log('Pausing ' + segment);
    if (segment == 'High') {
        tunerManualHighPaused = true;
    };
    if (segment == 'Medium') {
        tunerManualMediumPaused = true;
    };
    if (segment == 'Low') {
        tunerManualLowPaused = true;
    };
    $('#tuner_manual_'+segment+'_pause_btn').html('Unpause');
    //TODO: Change button color to solid
    document.getElementById('tuner_manual_'+segment+'_pause_btn').className = "btn btn-info btn-block";
    //TODO: Change onClick to tunerManualUnpause(segment) 
    document.getElementById('tuner_manual_'+segment+'_pause_btn').onclick = function () { tunerManualUnpause(segment); };
    tunerManualCheckComplete();
};

function tunerManualUnpause(segment) {
    //console.log('UnPausing ' + segment);
    if (segment == 'High') {
        tunerManualHighPaused = false;
    };
    if (segment == 'Medium') {
        tunerManualMediumPaused = false;
    };
    if (segment == 'Low') {
        tunerManualLowPaused = false;
    };
    $('#tuner_manual_'+segment+'_pause_btn').html('Pause');
    //TODO: Change button color to solid
    document.getElementById('tuner_manual_'+segment+'_pause_btn').className = "btn btn-outline-info btn-block";
    //TODO: Change onClick to tunerManualUnpause(segment) 
    document.getElementById('tuner_manual_'+segment+'_pause_btn').onclick = function () { tunerManualPause(segment); };
    tunerManualCheckComplete();
};

function tunerManualCheckComplete() {
    // Check if all criteria for finishing / calculating results are entered
    if (tunerManualHighPaused && tunerManualMediumPaused && tunerManualLowPaused) {
        $("#tuner_manual_finish_btn").prop('disabled', false);
    } else {
        $("#tuner_manual_finish_btn").prop('disabled', true);
    };
};

function tunerManualFinish() {
    tunerManualHighTemp = $('#tuner_manual_input_High_t').val();
    tunerManualHighTr = $('#tuner_manual_input_High_tr').val();
    tunerManualMediumTemp = $('#tuner_manual_input_Medium_t').val();
    tunerManualMediumTr = $('#tuner_manual_input_Medium_tr').val();
    tunerManualLowTemp = $('#tuner_manual_input_Low_t').val();
    tunerManualLowTr = $('#tuner_manual_input_Low_tr').val();

    if((tunerManualHighTemp >= 0) && (tunerManualMediumTemp >= 0) && (tunerManualLowTemp >= 0)) {
        $('#tuner_finish_btn_row').hide(); // Hide Finish Button
        $('#tuner_manual_High_pause_btn').prop('disabled', true);  // Disable pause buttons
        $('#tuner_manual_Medium_pause_btn').prop('disabled', true);  // Disable pause buttons
        $('#tuner_manual_Low_pause_btn').prop('disabled', true);  // Disable pause buttons

        clearInterval(tunerFetchTrValues); // Stop gathering data
        // Get all data 
        postdata = {
            'command' : 'manual_finish',
            'tunerManualHighTemp' : tunerManualHighTemp,
            'tunerManualHighTr' : tunerManualHighTr,
            'tunerManualMediumTemp' : tunerManualMediumTemp,
            'tunerManualMediumTr' : tunerManualMediumTr,
            'tunerManualLowTemp' : tunerManualLowTemp,
            'tunerManualLowTr' : tunerManualLowTr,
        };
        
        $.ajax({
            url : '/tuner',
            type : 'POST',
            data : JSON.stringify(postdata),
            contentType: "application/json; charset=utf-8",
            traditional: true,
            success: function (data) {
                //console.log('Call Success: ');
                //console.log(' - labels: ' + data.labels);
                //console.log(' - data:   ' + data.chart_data);
                //console.log(' - a:      ' + data.coefficients.a);
                //console.log(' - b:      ' + data.coefficients.b);
                //console.log(' - c:      ' + data.coefficients.c);
                tunerRunning = false;

                $('#tuner_profile_A').val(data.coefficients.a);
                $('#tuner_profile_B').val(data.coefficients.b);
                $('#tuner_profile_C').val(data.coefficients.c);
                tunerResultsChart.data.labels = data.labels;
                tunerResultsChart.data.datasets[0].data = data.chart_data;
                tunerResultsChart.update();
                if (data.chart_data.length != 0) {
                    // Show the chart if data exists
                    $('#tunerResultsChartWrapper').show();
                    $('#tunerResultsChartFailed').hide();
                } else {
                    // If no data was returned, unable to display chart
                    $('#tunerResultsChartFailed').show();
                    $('#tunerResultsChartWrapper').hide();
                };
                $('#tunerSaveApplyBtn').val(tunerProbeSelected);  // Update the Save & Apply button with Probe name
                $('#tuner_finish_row').show();
            }
        });
    };

};

// === Auto Tuner Functions ===
function tunerAutoInstructions() {
    // User Selected Auto Tuning Mode 
    // Hide Welcome Row & Show Manual Tuning Instructions 
    $("#tuner_welcome_row").hide();
    $("#tuner_back_to_welcome_row").show();
    var senddata = {
		'command' : 'render',
		'value' : 'auto_instruction_card',
	};
	$('#tuner_instruction_row').load('/tuner', senddata);
    $('#tuner_instruction_row').show();
};

function tunerAutoSelectProbe(sel) {
    tunerProbeSelected = sel.value;
    tunerProbeSelectedName = sel.options[sel.selectedIndex].text;

    tunerAutoCheckStartReqs();
};

function tunerAutoSelectReference(sel) {
    tunerProbeReference = sel.value;
    tunerProbeReferenceName = sel.options[sel.selectedIndex].text;

    tunerAutoCheckStartReqs();
};

function tunerAutoCheckStartReqs() {
    // Start button is disabled until the user selects a probe to tune and reference
    if ((tunerProbeSelected != 'none') && (tunerProbeReference != 'none') && (tunerProbeSelected != tunerProbeReference)){
        $("#tuner_auto_start_btn").prop('disabled', false);
    } else {
        $("#tuner_auto_start_btn").prop('disabled', true);
    };
};

function tunerStartAutoTool() {
    tunerRunning = true;

    // Hide the instructions and start the Autotune Tool
    $("#tuner_instruction_row").hide();
    $("#tuner_back_to_welcome_row").show();

    $('#tuner_auto_tool_title_probe_selected').html(tunerProbeSelectedName);
    $('#tuner_auto_tool_title_probe_reference').html(tunerProbeReferenceName);
    $("#tuner_tool_auto_title_row").show();

    var senddata = {
		'command' : 'render',
		'value' : 'auto_tool',
	};
	$('#tuner_tool_row').load('/tuner', senddata);
    $("#tuner_tool_row").show();

    var senddata = {
		'command' : 'render',
		'value' : 'auto_finish_btn',
	};
	$('#tuner_finish_btn_row').load('/tuner', senddata);
    $("#tuner_finish_btn_row").show();

    tunerAutoStatus = setInterval(tunerAutoUpdateStatus,1000);
};

function tunerAutoFinish() {
    $('#tuner_finish_btn_row').hide(); // Hide Finish Button
    clearInterval(tunerAutoStatus); // Stop gathering data
    document.getElementById("tunerAutoIcon").classList.remove('fa-spin');

    // Get all data 
    postdata = {
        'command' : 'auto_finish',
        'tunerManualHighTemp' : tunerManualHighTemp,
        'tunerManualHighTr' : tunerManualHighTr,
        'tunerManualMediumTemp' : tunerManualMediumTemp,
        'tunerManualMediumTr' : tunerManualMediumTr,
        'tunerManualLowTemp' : tunerManualLowTemp,
        'tunerManualLowTr' : tunerManualLowTr,
    };
        
    $.ajax({
        url : '/tuner',
        type : 'POST',
        data : JSON.stringify(postdata),
        contentType: "application/json; charset=utf-8",
        traditional: true,
        success: function (data) {
            //console.log('Call Success: ');
            //console.log(' - labels: ' + data.labels);
            //console.log(' - data:   ' + data.chart_data);
            //console.log(' - a:      ' + data.coefficients.a);
            //console.log(' - b:      ' + data.coefficients.b);
            //console.log(' - c:      ' + data.coefficients.c);
            tunerRunning = false;

            $('#tuner_profile_A').val(data.coefficients.a);
            $('#tuner_profile_B').val(data.coefficients.b);
            $('#tuner_profile_C').val(data.coefficients.c);
            tunerResultsChart.data.labels = data.labels;
            tunerResultsChart.data.datasets[0].data = data.chart_data;
            tunerResultsChart.update();
            if (data.chart_data.length != 0) {
                // Show the chart if data exists
                $('#tunerResultsChartWrapper').show();
                $('#tunerResultsChartFailed').hide();
            } else {
                // If no data was returned, unable to display chart
                $('#tunerResultsChartFailed').show();
                $('#tunerResultsChartWrapper').hide();
            };
            $('#tunerSaveApplyBtn').val(tunerProbeSelected);  // Update the Save & Apply button with Probe name
            $('#tuner_finish_row').show();
        }
    });
};



// === Generic Tuner Functions ===

function tunerUpdateTr() {
    var postdata = {
        'probe_selected' : tunerProbeSelected,
        'command' : 'read_tr'
    };

    $.ajax({
        url : '/tuner',
        type : 'POST',
        data : JSON.stringify(postdata),
        contentType: "application/json; charset=utf-8",
        traditional: true,
        success: function (data) {
            if (tunerManualHighPaused == false) {
                $("#tuner_manual_input_High_tr").val(data.trohms);
            };
            if (tunerManualMediumPaused == false) {
                $("#tuner_manual_input_Medium_tr").val(data.trohms);
            };
            if (tunerManualLowPaused == false) {
                $("#tuner_manual_input_Low_tr").val(data.trohms);
            };
        }
    });
};

function tunerAutoUpdateStatus() {
    var postdata = {
        'probe_selected' : tunerProbeSelected,
        'probe_reference' : tunerProbeReference,
        'command' : 'read_auto_status'
    };

    $.ajax({
        url : '/tuner',
        type : 'POST',
        data : JSON.stringify(postdata),
        contentType: "application/json; charset=utf-8",
        traditional: true,
        success: function (data) {
            $('#tuner_auto_ref_temp').html(data.current_temp);
            $('#tuner_auto_probe_tr').html(data.current_tr);
            $('#tuner_auto_high_tr').html(data.high_tr);
            $('#tuner_auto_medium_tr').html(data.medium_tr);
            $('#tuner_auto_low_tr').html(data.low_tr);
            $('#tuner_auto_high_temp').html(data.high_temp);
            $('#tuner_auto_medium_temp').html(data.medium_temp);
            $('#tuner_auto_low_temp').html(data.low_temp);

            tunerManualHighTr = data.high_tr;
            tunerManualHighTemp = data.high_temp;
            tunerManualMediumTr = data.medium_tr;
            tunerManualMediumTemp = data.medium_temp;
            tunerManualLowTr = data.low_tr;
            tunerManualLowTemp = data.low_temp;

            if (data.ready) {
                $('#tuner_auto_finish_btn').prop('disabled', false);
            } else {
                $('#tuner_auto_finish_btn').prop('disabled', true);
            };
        }
    });
};

// === Listeners ===
// Adapted from https://stackoverflow.com/questions/4945932/window-onbeforeunload-ajax-request-in-chrome
// Written by Stack Overflow user Mohoch 
function pageCleanup()
{
    clearInterval(tunerFetchTrValues);
    clearInterval(tunerAutoStatus);
    //console.log('Page Cleanup Run. Tuner Running: ' + tunerRunning);

    if (!_wasPageCleanedUp)
    {
        postdata = {
            'command' : 'stop_tuning'
        };
        $.ajax({
            type: 'POST',
            async: false,
            url: '/tuner',
            data : JSON.stringify(postdata),
            contentType: "application/json; charset=utf-8",
            traditional: true,
            success: function ()
            {
                _wasPageCleanedUp = true;
                tunerRunning = false;
            }
        });
    }
}

$(window).on('beforeunload', function ()
{
    //this will work only for Chrome
    pageCleanup();
});

$(window).on("unload", function ()
{
    //this will work for other browsers
    pageCleanup();
});


// === Document Ready ===
$(document).ready(function(){
    tunerCheckState();
}); // End of Document Ready Function 
    