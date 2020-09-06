
$(document).ready( function(){
$('#refreshmedata').load('/data');
refreshme();
});

function refreshme()
{
	setTimeout( function() {
	  $('#refreshdata').fadeOut('fast').load('/data').fadeIn('fast');
	  refreshme();
	}, 10000);
}
