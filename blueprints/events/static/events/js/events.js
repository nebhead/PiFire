// events.js 
//  - Loads paginated list of events

// Variables to keep track of current settings
var currentPage = 1;  // Start on page 1
var reverseOrder = true;  // Display in reverse order i.e. last event first
var itemsDisplayed = 25;  // Display 25 items per page default

$(document).ready(function(){ 
	// Load the initial paginated event list
	var senddata = { 
		'eventslist' : true,
		'page' : currentPage, 
		'reverse' : reverseOrder, 
		'itemsperpage' : itemsDisplayed
	};
	$('#events_list').load('/events', senddata);
    
    // SetInterval to reload every 4 seconds
	var eventsInterval = setInterval(function() {
        var senddata = { 
            'eventslist' : true,
            'page' : currentPage, 
            'reverse' : reverseOrder, 
            'itemsperpage' : itemsDisplayed
        };
        $('#events_list').load('/events', senddata);
    }, 4000);
});

function gotoPage(pagenum, sortorder, itemsperpage) {
    currentPage = pagenum;
    reverseOrder = sortorder;
    itemsDisplayed = itemsperpage;
    // Load updated paginated data
	var senddata = { 
		'eventslist' : true,
		'page' : pagenum, 
		'reverse' : sortorder, 
		'itemsperpage' : itemsperpage
	};
	$('#events_list').load('/events', senddata)
};
