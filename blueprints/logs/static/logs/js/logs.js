// logs.js 
//  - Loads paginated list of lines from log files 

// Variables to keep track of current settings
var currentPage = 1;  // Start on page 1
var reverseOrder = false;  // Display in reverse order i.e. last event first
var itemsDisplayed = 100;  // Display 25 items per page default

$(document).ready(function(){ 
	//console.log('Page Loaded.');
});

function getData(selectFile) {
	logfile = selectFile.value;
	//console.log('logfile selected: ' + logfile);

	currentPage = 1;  // Start on page 1
	reverseOrder = false;  // Display in reverse order i.e. last event first

	// Load Log File Data 
	var senddata = { 
		'eventslist' : true,
		'page' : currentPage, 
		'reverse' : reverseOrder, 
		'itemsperpage' : itemsDisplayed,
		'logfile' : logfile
	};
	$('#logs_list').load('/logs', senddata);
};

function gotoPage(pagenum, sortorder, itemsperpage, logfile) {
    currentPage = pagenum;
    reverseOrder = sortorder;
    itemsDisplayed = itemsperpage;

    // Load updated paginated data
	var senddata = { 
		'eventslist' : true,
		'page' : pagenum, 
		'reverse' : sortorder, 
		'itemsperpage' : itemsperpage,
		'logfile' : logfile
	};
	$('#logs_list').load('/logs', senddata)
};
