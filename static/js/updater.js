$(document).ready(function(){
	req = $.ajax({
		url : '/checkupdate',
		type : 'GET'
	});
	req.done(function(data) {
		if(data['result'] != 'success') {
			//console.log(data)
			$('#update_checking').hide();
			$('#update_failed').show();
		} else {
			//console.log(data)
			if(data['behind'] != 0) {
				$('#update_checking').hide();
				$('#commits_behind').html(data['behind']);
				$('#show_log').val(data['behind']);
				$('#update_available').show();
			} else {
				$('#update_checking').hide();
				$('#update_current').show();
			}
		};
	});
  });

$( "#check_for_update" ).click(function() {
	$('#update_current').hide();
	$('#update_failed').hide();
	$('#update_checking').show();
	req = $.ajax({
		url : '/checkupdate',
		type : 'GET'
	});
	req.done(function(data) {
		if(data['result'] != 'success') {
			//console.log(data)
			$('#update_checking').hide();
			$('#update_failed').show();
		} else {
			//console.log(data)
			if(data['behind'] != 0) {
				$('#update_checking').hide();
				$('#commits_behind').html(data['behind']);
				$('#show_log').val(data['behind']);
				$('#update_available').show();
			} else {
				$('#update_checking').hide();
				$('#update_current').show();
			}
		};
	});
});

$( "#check_for_update_2" ).click(function() {
	$( "#check_for_update" ).click();
});