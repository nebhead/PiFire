// Init Global Variables
var annotation_list = [];
var annotation_enabled = true;
var probe_mapper;
var removeMediaMap;
var temperatureCharts = new Chart(document.getElementById('HistoryChart'), {
	type: 'line',
	data: {
		labels: [],
		datasets: []
	},
	options: {
		plugins: {
			legend: {
				labels: {
					usePointStyle: true,
				}
			}, 
			annotation: {
				annotations: []
			},
			zoom: {
				limits: {
					y: {min: -30, max: 600}
				  },
				pan: {
					enabled: true,
					mode: 'xy',
				  },
				zoom: {
				  wheel: {
					enabled: true,
				  },
				  pinch: {
					enabled: true
				  },
				  mode: 'xy',
				}
			},
			title: {
				display: true,
				position: 'bottom',
				text: 'Zoom: Scroll Wheel or Pinch 		Pan: Click & Drag'
			}
		},
		scales: {
			x: {
				type: 'time'
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

// Functions

// Edit Labels
function editLabel(old_label) {
	var new_label_id = '#' + old_label + '_label';
	var new_label = $(new_label_id).val();
	var postdata = { 
		'graph_labels' : true,
		'filename' : cookfilename, 
		'old_label' : old_label,
		'new_label' : new_label	
	};
	//console.log(postdata);

	req = $.ajax({
		url : '/updatecookfile',
		type : 'POST',
		data : JSON.stringify(postdata),
		contentType: "application/json; charset=utf-8",
		traditional: true,
		success: function (data) {
			if(data.result == 'OK') {
				new_label_safe = data.new_label_safe; //new safe label
				refreshChart();

				// Fix-up label id's
				document.getElementById(old_label+'_name').id = new_label_safe+'_name';
				document.getElementById(new_label_safe+'_name').innerHTML = new_label;
				document.getElementById(old_label+'_label').id = new_label_safe+'_label';
				document.getElementById(old_label+'_saveLabel').setAttribute("onclick","editLabel('"+new_label_safe+"')");
				document.getElementById(old_label+'_saveLabel').id = new_label_safe+'_saveLabel';
				$(new_label_id).fadeOut(250).fadeIn(500);
			} else {
				var error = data.result;
				console.log('Response: ' + error);
				alert('An error occurred.  Try again later.');
			};
		}
	});
};

function refreshChart() {
	// Load graph data and update page 
	var postdata = { 
		'full_graph' : true,
		'filename' : cookfilename	
	};
	req = $.ajax({
		url : '/cookfiledata',
		type : 'POST',
		data : JSON.stringify(postdata),
		contentType: "application/json; charset=utf-8",
		traditional: true,
		success: function (data) {
				// Hide Loading Message
				$('#loadingmessage').hide();

				// Build Chart Data from Response
				temperatureCharts.data.labels = data.time_labels;
				temperatureCharts.data.datasets = data.chart_data;
				annotation_list = data.annotations;
				temperatureCharts.options.plugins.annotation.annotations = annotation_list;
				probe_mapper = data.probe_mapper;

				// Update the chart
				temperatureCharts.update();
			}
	});
};

// On Document Ready
$(document).ready(function(){
	refreshChart();

	$("#annotation_enabled").change(function() {
		if(document.getElementById('annotation_enabled').checked) {
			annotation_enabled = true;
		} else {
			annotation_enabled = false;
		};

		if (annotation_enabled == true) {
			temperatureCharts.options.plugins.annotation.annotations = annotation_list;
		} else {
			temperatureCharts.options.plugins.annotation.annotations = {};
		};			
		// Update Chart
		temperatureCharts.update();
	});

	// Reset Zoom on Graph
	$("#resetzoom").click(function() {
		temperatureCharts.resetZoom();
	});

	// Edit Title
	$("#editTitle").click(function() {
		var title = $("#cookfileTitle").val();
		var postdata = { 
			'metadata' : true,
			'filename' : cookfilename, 
			'editTitle' : title 	
		};
		req = $.ajax({
			url : '/updatecookfile',
			type : 'POST',
			data : JSON.stringify(postdata),
			contentType: "application/json; charset=utf-8",
			traditional: true,
			success: function (data) {
				if(data.result == 'OK') {
					$("#cookfileTitle").fadeOut(250).fadeIn(500);
				} else {
					var error = data.result;
					console.log('Response: ' + error);
					alert('An error occurred.  Try again later.');
				};
			}
		});
	});

	// Add a new comment
	$("#addcomment").click(function() {
		commenttext = $("#newcommenttext").val();
		var postdata = { 
			'comments' : true,
			'filename' : cookfilename, 
			'commentnew' : commenttext 	
		};
		req = $.ajax({
			url : '/updatecookfile',
			type : 'POST',
			data : JSON.stringify(postdata),
			contentType: "application/json; charset=utf-8",
			traditional: true,
			success: function (data) {
				if(data.result == 'OK') {
					newcommentid = data.newcommentid;
					newcommentdt = data.newcommentdt;
					var commentcard = '<div class="card shadow" id="'+ newcommentid +'">';
					commentcard +='<div class="card-header" id="';
					commentcard +=newcommentid + '_header';
					commentcard +='"><strong>'+ newcommentdt +'</strong></div>';
					commentcard +='<div class="card-body" id="';
					commentcard +=newcommentid + '_body';
					commentcard +='">'+ commenttext +'</div>';
					commentcard +='<div class="row justify-content-md-center" id="media_for_' + newcommentid + '"></div>';
					commentcard +='<div class="card-footer" id="'; 
					commentcard +=newcommentid + '_footer';
					commentcard +='">';
					commentcard +='<button class="btn btn-primary btn-sm text-white float-right" type="button" id="managemediabutton" data-val="' + newcommentid + '" data-toggle="modal" data-target="#managemediamodal"><i class="fas fa-photo-video"></i>&nbsp; Attach Media</button>';
					commentcard +='<button class="btn btn-success btn-sm text-white" type="button" id="';
					commentcard +=newcommentid + '_savebutton"';
					commentcard +='" onclick="saveComment(\''+ newcommentid +'\')" style="display:none"><i class="fas fa-save"></i>&nbsp; Save</button>&nbsp';
					commentcard +='<button class="btn btn-primary btn-sm text-white" type="button" id="';
					commentcard +=newcommentid + '_editbutton"';
					commentcard +='onclick="editComment(\''+ newcommentid +'\')"><i class="fas fa-edit"></i>&nbsp; Edit</button>&nbsp';
					commentcard +='<button class="btn btn-danger btn-sm text-white" type="button" id="delcomment" data-val="';
					commentcard +=newcommentid +'" data-toggle="modal" data-target="#delcommentmodal"><i class="far fa-trash-alt"></i>&nbsp; Delete</button>';
					commentcard +='</div></div><br>';
					$("#newcommentcard").before(commentcard);
					$("#newcommenttext").val('');
				} else {
					var error = data.result;
					console.log('Response: ' + error);
					alert('An error occurred.  Try again later.');
				};
			}
		});
	})

	// Delete a new comment
	$('#delcommentmodal').on('show.bs.modal', function (event) {
		var commentidselected = $(event.relatedTarget).data('val');
	   	$('#delcommentid').val(commentidselected);
	});

	$('#delcommentid').click(function() {
		var commentidselected = $('#delcommentid').val();
		var postdata = { 
			'comments' : true,
			'filename' : cookfilename, 
			'delcomment' : commentidselected 	
		};
		req = $.ajax({
			url : '/updatecookfile',
			type : 'POST',
			data : JSON.stringify(postdata),
			contentType: "application/json; charset=utf-8",
			traditional: true,
			success: function (data) {
				if(data.result == 'OK') {
					$('#'+commentidselected).remove();
				} else {
					var error = data.result;
					console.log('Response: ' + error);
					alert('An error occurred.  Try again later.');
				};
			}
		});
	});

	// Manage Media Modal Selected
	$('#managemediamodal').on('show.bs.modal', function (event) {
		var commentid = $(event.relatedTarget).data('val');
		$('#managemedia_id').val(commentid);
		// Clear out any previous HTML
		$('#managemedia_content').html('');
		var postdata = { 
			'managemediacomment' : true,
			'cookfilename' : cookfilename, 
			'commentid' : commentid
		};
		req = $.ajax({
			url : '/cookfiledata',
			type : 'POST',
			data : JSON.stringify(postdata),
			contentType: "application/json; charset=utf-8",
			traditional: true,
			success: function (data) {
				if(data.result == 'OK') {
					for (let i = 0; i < data.assetlist.length; i++) {
						media_id = 'media_' + data.assetlist[i].assetid;
						thumbfilename = data.assetlist[i].assetname;
						// Column
						html = '<div class="col" onclick=';
						html += '"toggleSelectImage(\'' + media_id + '\', \'' + thumbfilename + '\', \'' + cookfilename + '\', \'' + commentid + '\')">';
						// Image
						html += '<img src="' + imagepath + cookfileID + '/thumbs/' + thumbfilename + '" ';
						if(data.assetlist[i].selected) {
							html += 'value="selected" class="border rounded shadow" ';
						} else {
							html += 'value="unselected" class="rounded" ';
						};
						html += 'alt="thumbnail" width="128" height="128" id="'+ media_id + '"> '; 
						// Closing
						html += '<br><br></div>'; 
						$('#managemedia_content').append(html);
						// Set the values because it's not being set above reliably
						if(data.assetlist[i].selected) {
							$('#'+media_id).val('selected');
						} else {
							$('#'+media_id).val('unselected');
						};
					}; 
				} else {
					var error = data.result;
					console.log('Response: ' + error);
					alert('An error occurred.  Try again later.');
				};
			}
		});
	});

	// Display Media Modal Selected
	$('#displaymediamodal').on('show.bs.modal', function (event) {
		var mediafile = $(event.relatedTarget).data('val');
		var commentid = $(event.relatedTarget).data('commentid');
		var html = showNavImage(imagepath, cookfileID, mediafile, commentid);
		$('#displaymedia_content').html(html);
	});

	// Remove/Delete Media Modal Selected
	$('#delmediaModal').on('show.bs.modal', function (event) {
		$('#delmedia_content').html('');
		var postdata = { 
			'getallmedia' : true,
			'cookfilename' : cookfilename, 
		};
		req = $.ajax({
			url : '/cookfiledata',
			type : 'POST',
			data : JSON.stringify(postdata),
			contentType: "application/json; charset=utf-8",
			traditional: true,
			success: function (data) {
				if(data.result == 'OK') {
					removeMediaMap = new Map();
					for (let i = 0; i < data.assetlist.length; i++) {
						media_id = 'delmedia_' + data.assetlist[i].assetid;
						thumbfilename = data.assetlist[i].assetname;
						removeMediaMap.set(thumbfilename, false);
						// Column
						html = '<div class="col">';
						html += '<div class="custom-control custom-checkbox">';
						html += '<input type="checkbox" class="custom-control-input" id="' + media_id +'"';
						html += 'onclick="registerRemoveItem(\''+ media_id +'\', \''+ thumbfilename +'\')">';
						html += '<label class="custom-control-label" for="'+ media_id +'">Remove</label>';
						html += '</div>';
						html += '<img src="' + imagepath + cookfileID + '/thumbs/' + thumbfilename + '" ';
						html += 'alt="thumbnail" width="128" height="128" class="border rounded">'; 
						// Closing
						html += '<br><br>';

						html += '</div>'; 
						$('#delmedia_content').append(html);
					};
					console.log(removeMediaMap); 
				} else {
					var error = data.result;
					console.log('Response: ' + error);
					alert('An error occurred.  Try again later.');
				};
			}
		});
	});
});

function registerRemoveItem(item_id, filename) {
	var togglestate = $('#'+item_id).is(":checked");
	if(togglestate) {
		removeMediaMap.set(filename, true);
	} else {
		removeMediaMap.set(filename, false);
	};
	// Convert selected items to list/array 
	var delete_list = [];
	for (const [key, value] of removeMediaMap) {
		if(value==true) {
			delete_list.push(key);
		};
	};
	$("#delAssetlist").val(delete_list);
};

function showNavImage(imagepath, cookfileID, mediafile, commentid) {
	var html = '';
	html += '<img src="' + imagepath + cookfileID + '/' + mediafile + '" class="rounded" alt="image">';
	html += '<button class="btn float-left" type="button" onclick="navImage(\''+ mediafile +'\', \'' + commentid + '\', \'prev\')"><i class="fas fa-chevron-left"></i></button>';
	html += '<button class="btn float-right" type="button" onclick="navImage(\''+ mediafile +'\', \'' + commentid + '\', \'next\')"><i class="fas fa-chevron-right"></i></button>';
	return html
};

function navImage(mediafilename, commentid, navigate) {
	console.log(navigate + ' Image');
	var postdata = { 
		'navimage' : navigate,
		'mediafilename' : mediafilename, 
		'commentid' : commentid,
		'cookfilename' : cookfilename 	
	};
	req = $.ajax({
		url : '/cookfiledata',
		type : 'POST',
		data : JSON.stringify(postdata),
		contentType: "application/json; charset=utf-8",
		traditional: true,
		success: function (data) {
			if(data.result == 'OK') {
				// Get image information
				var mediafile = data.mediafilename;
				var html = showNavImage(imagepath, cookfileID, mediafile, commentid);
				$('#displaymedia_content').html(html);
			} else {
				var error = data.result;
				console.log('Response: ' + error);
				alert('An error occurred.  Try again later.');
			};
		}
	});
};

function editComment(commentid) {
	var postdata = { 
		'comments' : true,
		'filename' : cookfilename, 
		'editcomment' : commentid 	
	};
	req = $.ajax({
		url : '/updatecookfile',
		type : 'POST',
		data : JSON.stringify(postdata),
		contentType: "application/json; charset=utf-8",
		traditional: true,
		success: function (data) {
			if(data.result == 'OK') {
				var commenttext = data.text;
				var commentedit = '<div class="input-group">';
				commentedit += '<div class="input-group-prepend">'; 
				commentedit += '<span class="input-group-text"><i class="fas fa-comment-alt"></i></span>'; 
				commentedit += '</div>'; 
				commentedit += '<textarea class="form-control" id="';
				commentedit += commentid + '_textarea';
				commentedit += '" rows="4">'; 
				commentedit += commenttext; 
				commentedit += '</textarea></div>';
				$("#"+commentid+"_editbutton").hide();
				$("#"+commentid+"_savebutton").show();
				$("#"+commentid+"_body").html(commentedit);
			} else {
				var error = data.result;
				console.log('Response: ' + error);
				alert('An error occurred.  Try again later.');
			};
		}
	});

};

function saveComment(commentid) {
	var commenttext = $("#"+commentid+"_textarea").val();
	var postdata = { 
		'comments' : true,
		'filename' : cookfilename, 
		'savecomment' : commentid, 
		'text' : commenttext 	
	};
	req = $.ajax({
		url : '/updatecookfile',
		type : 'POST',
		data : JSON.stringify(postdata),
		contentType: "application/json; charset=utf-8",
		traditional: true,
		success: function (data) {
			if(data.result == 'OK') {
				var commenttext = data.text;
				$("#"+commentid+"_editbutton").show();
				$("#"+commentid+"_savebutton").hide();
				$("#"+commentid+"_body").html(commenttext);
				var headertext = '<strong>';
				headertext += data.datetime;
				headertext += '</strong><span class="badge badge-info float-right">Edited ';
				headertext += data.edited;
				headertext += '</span>';
				$("#"+commentid+"_header").html(headertext);
			} else {
				var error = data.result;
				console.log('Response: ' + error);
				alert('An error occurred.  Try again later.');
			};
		}
	});
};

function toggleSelectImage(tag, filename, cookfilename, commentid) {
	var select_state = document.getElementById(tag).value;

	console.log(select_state)

	var postdata = { 
		'media' : true,
		'filename' : cookfilename, 
		'commentid' : commentid, 
		'assetfilename' : filename, 
		'state' : select_state
	};
	req = $.ajax({
		url : '/updatecookfile',
		type : 'POST',
		data : JSON.stringify(postdata),
		contentType: "application/json; charset=utf-8",
		traditional: true,
		success: function (data) {
			if(data.result == 'OK') {
				if(select_state == 'selected') {
					document.getElementById(tag).className = "rounded";
					$('#'+tag).val('unselected');
				} else {
					document.getElementById(tag).className = "border rounded shadow";
					$('#'+tag).val('selected');
				};
				updateCommentThumbs(commentid);		
			} else {
				var error = data.result;
				console.log('Response: ' + error);
				alert('An error occurred.  Try again later.');
			};
		}
	});
};

function displayAssetThumb(mediafilename, commentid) {
	var html = '';
	html += '<div class="col text-center">';
	html += '<button class="btn" type="button" data-val="' + mediafilename + '" data-commentid="' + commentid + '" data-toggle="modal" data-target="#displaymediamodal">';
	html += '<img src="'+ imagepath + cookfileID + '/thumbs/' + mediafilename + '" class="rounded" alt="thumbnail" width="128" height="128">';
	html += '</button><br><br></div>';
	return html;
};

function updateCommentThumbs(commentid) {
	var postdata = { 
		'getcommentassets' : true,
		'commentid' : commentid, 
		'cookfilename' : cookfilename 
	};
	req = $.ajax({
		url : '/cookfiledata',
		type : 'POST',
		data : JSON.stringify(postdata),
		contentType: "application/json; charset=utf-8",
		traditional: true,
		success: function (data) {
			if(data.result == 'OK') {
				// Get image information
				var assetlist = data.assetlist;
				var tag = 'media_for_' + commentid;
				var html = '';
				// Clear existing images
				$('#'+tag).html(html);
				for (let i = 0; i < assetlist.length; i++) {
					html = displayAssetThumb(assetlist[i], commentid);
					$('#'+tag).append(html);
				};
			} else {
				var error = data.result;
				console.log('Response: ' + error);
				alert('An error occurred.  Try again later.');
			};
		}
	});

};