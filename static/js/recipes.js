// Global Variables 
var recipe_selected = '';
const RECIPE_FOLDER = './recipes/';
var recipeRunStatusInterval;
var recipeMode = 'PageLoad';
var recipeAssetsList = [];
// === Listeners ===

// Load Recipe Book Menu
$('#recipe_loadmenu_btn, #recipe_toolbar_loadmenu_btn').click(function(){
	recipeBook();
});

// Run Recipe Button
$('#recipe_toolbar_run_btn').click(function(){
	recipeRunFile(recipe_selected);
});

// Edit Recipe Button
$('#recipe_toolbar_edit_btn').click(function(){
	recipeEditFile(recipe_selected);
});

// New Recipe Button
$('#recipe_new_btn, #recipe_toolbar_new_btn').click(function(){
	recipeEditFile('');
});

// Upload Recipe File Button 
$('#recipe_file_upload_btn').click(function(){
	const formData = new FormData();
	const files = document.getElementById("upload_recipe_file");
	formData.append("recipefile", files.files[0]);
	formData.append("upload", true);

	const requestOptions = {
		headers: {
			"Content-Type": files.files[0].contentType, // Content-Type matches the content type of the file
		},
		mode: "no-cors",
		method: "POST",
		files: files.files[0],
		body: formData,
	};

	fetch("/recipedata/upload", requestOptions).then(
	(response) => {
		recipeBook(); // Reload the recipe book when completed uploading
	}
	);
});

// Display Media Modal Selected
$('#display_asset_modal').on('show.bs.modal', function (event) {
	var asset_filename = $(event.relatedTarget).data('assetfilename');
	var recipe_filename = $(event.relatedTarget).data('recipefilename');
	var section = $(event.relatedTarget).data('section');
	var section_index = $(event.relatedTarget).data('sectionindex');

	var senddata = {
		'recipeshowasset' : true,
		'filename' : recipe_filename,
		'asset' : asset_filename, 
		'section' : section, 
		'section_index' : section_index, 
	};
	//console.log(senddata);
	$('#display_asset_content').load('/recipedata', senddata);
});

   // === Functions === 

function recipeWelcome() {
	// Hide inactive rows
	$('#recipe_toolbar_row, #recipe_load_row, #recipe_show_row, #recipe_assets_row, #recipe_run_status_row').hide();
	$('#recipe_welcome_row').show();
};

function recipeBook() {
	recipeCheckStateStop();
	recipe_selected = ''; // Clear recipe selected field
	// Load the paginated recipe file list
	gotoRFPage(1, false, 10);
	// Hide inactive rows
	$('#recipe_welcome_row, #recipe_show_row, #recipe_assets_row, #recipe_run_status_row').hide();
	// Setup and show the recipe toolbar items 
	$('#recipe_toolbar_loadmenu_col, #recipe_toolbar_edit_col, #recipe_toolbar_run_col').hide();
	$('#recipe_toolbar_new_col').show();
	$('#recipe_toolbar_row').slideDown();
	// Show the recipe load row 
	$('#recipe_load_row').fadeIn(500);
};

function recipeManageAssets(filename, section, index) {
	// Hide inactive rows
	$('#recipe_welcome_row, #recipe_show_row, #recipe_load_row, #recipe_run_status_row').hide();
	// Setup and show the recipe toolbar items 
	$('#recipe_toolbar_row').slideUp();
	// Show the recipe asset row 
	if (filename == '') {
		filename = recipe_selected;
	};
	var senddata = { 
		'recipeassetmanager' : true,
		'section' : section, 
		'index' : index,
		'filename' : filename
	};
	$('#recipe_assets_row').load('/recipedata', senddata).fadeIn(500);
};

function recipeImageSelectToggle(filename, section, section_index, asset_name, asset_id) {
	var status = $('#asset_highlight_'+asset_id).val();
	//console.log('Before - Assets ' + asset_id + ': ' + status);
	var senddata = {
		'assetchange' : true,
		'section' : section, 
		'index' : section_index,
		'filename' : filename, 
		'asset_name' : asset_name, 
		'asset_id' : asset_id,
		'action' : 'none'
	};

	if(status == 'true') {
		// Remove Asset
		$('#asset_select_'+asset_id).html('<h3><i class="far fa-circle"></i></h3>');
		$('#asset_highlight_'+asset_id).val('false');
		if(section == 'splash') {
			senddata['action'] = 'remove';
			recipeAssetsEdit(senddata);
			var delayRefresh = setInterval(function(){
				recipeManageAssets(filename, section, section_index);
				clearInterval(delayRefresh);
			}, 300);
		} else if (section == 'delete') {
			senddata['action'] = 'remove';
			recipeAssetsEdit(senddata);
			//console.log('Deleting: '+ asset_name);
			var delayRefresh = setInterval(function(){
				recipeManageAssets(filename, section, section_index);
				clearInterval(delayRefresh);
			}, 300);
		} else {
			senddata['action'] = 'remove';
			recipeAssetsEdit(senddata);
		};
	} else {
		// Add Asset 
		$('#asset_select_'+asset_id).html('<h3><i class="fas fa-check-circle"></i></h3>');
		$('#asset_highlight_'+asset_id).val('true');
		if(section == 'splash') {
			senddata['action'] = 'add';
			recipeAssetsEdit(senddata);
			var delayRefresh = setInterval(function(){
				recipeManageAssets(filename, section, section_index);
				clearInterval(delayRefresh);
			}, 300);
		} else if (section == 'delete') {
			senddata['action'] = 'remove';
			recipeAssetsEdit(senddata);
			//console.log('Deleting: '+ asset_name);
			var delayRefresh = setInterval(function(){
				recipeManageAssets(filename, section, section_index);
				clearInterval(delayRefresh);
			}, 300);
		} else {
			senddata['action'] = 'add';
			recipeAssetsEdit(senddata);
		};
	};
	//console.log('After - Assets ' + asset_id + ': ' + $('#asset_highlight_'+asset_id).val());
};

function recipeAssetsEdit(senddata) {
	$.ajax({
        url : '/recipedata',
        type : 'POST',
        data : JSON.stringify(senddata),
        contentType: "application/json; charset=utf-8",
        traditional: true,
        success : function (result) {
            // Relevant data returned from call:
            //  result.result
			if(result.result != 'success') {
				alert('Asset Update Failed.')
			};
		}
    });
};

// Upload Recipe Assets
function recipeUploadAssets(filename, section, section_index) {
	//console.log('Attempting File Upload Images');
	const fileInput = document.getElementById("upload_recipe_assets");
	
	var fileList = [];
	var fileCount = fileInput.files.length;
	for (var i = 0; i < fileInput.files.length; i++) {
	  fileList.push(fileInput.files[i]);
  	};

	var fileCounter = 0;
	fileList.forEach(function (file) {
		const formData = new FormData();
		formData.append("assetfiles", file);
		formData.append("uploadassets", true);
		formData.append("filename", filename);
	
		const requestOptions = {
			headers: {
				"Content-Type": file.contentType, // Content-Type matches the content type of the file
			},
			mode: "no-cors",
			method: "POST",
			files: file,
			body: formData,
		};

		fetch("/recipedata/upload", requestOptions).then(
			(response) => {
				fileCounter += 1;
				//console.log('Uploaded File # ' + fileCounter)
			}
		);
    });
	var uploadCompleted = setInterval(function(){
		if(fileCounter == fileCount) {
			//console.log('Uploads completed.  Reloading asset manager.')
			recipeManageAssets(filename, section, section_index);
			clearInterval(uploadCompleted);
		};
	}, 100);
};

function recipeDeleteFile(delete_this) {
	postdata = {
		'deletefile' : true, 
		'filename' : delete_this
	};
	$.ajax({
        url : '/recipedata',
        type : 'POST',
        data : JSON.stringify(postdata),
        contentType: "application/json; charset=utf-8",
        traditional: true,
        success : function (result) {
            // Relevant data returned from call:
            //  result.result
			if(result.result == 'success') {
				// reload Recipe Book
				recipeBook();
			} else {
				alert('File Delete Failed.')
			};
		}
    });
};

function recipeRunFile(filename) {
	// Hide inactive rows
	$('#recipe_welcome_row, #recipe_load_row, #recipe_show_row, #recipe_assets_row').hide();
	// Setup and show the recipe toolbar items 
	$('#recipe_toolbar_run_col').hide();
	$('#recipe_toolbar_loadmenu_col, #recipe_toolbar_edit_col, #recipe_toolbar_new_col').show();
	$('#recipe_toolbar_row').slideDown();
	
	// Send Run Recipe Command to API 
	var postdata = {
		'updated' : true, 
		'mode' : 'Recipe', 
		'recipe' : {
			'filename' : RECIPE_FOLDER+filename
		}
	};
    $.ajax({
        url : '/api/control',
        type : 'POST',
        data : JSON.stringify(postdata),
        contentType: "application/json; charset=utf-8",
        traditional: true,
        success: function (data) {
            //console.log('API Post Call: ' + data.control);
			var recipeDelayCall = setInterval(function() {
				recipeRunStatus(filename);
				recipeRunStatusInterval = setInterval(function(){
					recipeRunStatus(filename);
				}, 4000);
				clearInterval(recipeDelayCall);
			}, 1000);
		}
    });
};

function recipeRunStatus(filename) {
	recipe_selected = filename;
	var senddata = {
		'reciperunstatus' : true,
		'filename' : filename
	};
	$('#recipe_run_status_row').load('/recipedata', senddata).fadeIn(500);
};

// Goto page in pagination of recipe files 
function gotoRFPage(pagenum, sortorder, itemsperpage) {
	// Load updated paginated data
	var senddata = { 
		'recipefilelist' : true,
		'page' : pagenum, 
		'reverse' : sortorder, 
		'itemsperpage' : itemsperpage
	};
	$('#recipefilelist').load('/recipedata', senddata)
};

// Open recipe file for viewing / running 
function recipeOpenFile(filename) {
	recipeCheckStateStop();
	//console.log('Opening: ' + filename);
	// Load updated paginated data
	var senddata = { 
		'recipeview' : true,
		'filename' : filename, 
	};
	recipe_selected = filename;
	$('#recipe_show_row').load('/recipedata', senddata)
	// Show active toolbar buttons 
	$('#recipe_toolbar_loadmenu_col, #recipe_toolbar_edit_col, #recipe_toolbar_new_col, #recipe_toolbar_run_col').show();
	// Hide the inactive rows 
	$('#recipe_welcome_row, #recipe_load_row, #recipe_assets_row, #recipe_run_status_row').hide();
	// Show the active row 
	$('#recipe_show_row').fadeIn(500);
};

// Open recipe file for viewing / running 
function recipeEditFile(filename) {
	recipeCheckStateStop();
	// Load updated paginated data
	var senddata = { 
		'recipeedit' : true,
		'filename' : filename
	};

	$('#recipe_show_row').load('/recipedata', senddata, function(responseTxt, statusTxt, xhr){
		if(statusTxt == "success")
			recipe_selected = $('#recipe_filename').val();
	  });
	// Hide unused rows
	$('#recipe_welcome_row, #recipe_load_row, #recipe_assets_row, #recipe_run_status_row').fadeOut(500);
	// Show the recipe load row 
	$('#recipe_toolbar_edit_col').hide();
	$('#recipe_toolbar_loadmenu_col, #recipe_toolbar_run_col, #recipe_toolbar_new_col').show();

	// Setup and show the recipe toolbar items 
	$('#recipe_toolbar_row').slideDown();

	// Show the recipe reader row 
	$('#recipe_show_row').fadeIn(500);
};

function metadataUpdate(field, value) {
	var senddata = {
		'update' : 'metadata',
		'field' : field,
		'value' : value,
		'filename' : recipe_selected
	};

	if(field == 'description') {
		$('#recipe_edit_description_row').fadeOut(500).load('/recipedata', senddata).fadeIn(500);
		$('#successToastMsg').html('Successfully updated description.');
		$('#successToast').toast('show');
	} else if (field == 'title') {
		$('#recipe_edit_title_row').fadeOut(500).load('/recipedata', senddata).fadeIn(500);
		$('#successToastMsg').html('Successfully updated title.');
		$('#successToast').toast('show');
	} else if (field == 'food_probes') {
		$('#recipe_edit_metadata_row').fadeOut(500).load('/recipedata', senddata).fadeIn(500);
		$('#successToastMsg').html('Successfully updated number of food probes.');
		$('#successToast').toast('show');
		var senddata = {
			'refresh' : 'steps',
			'filename' : recipe_selected
		};
		$('#recipe_edit_steps_row').load('/recipedata', senddata);
	} else {
		$('#recipe_edit_metadata_row').fadeOut(500).load('/recipedata', senddata).fadeIn(500);
		$('#successToastMsg').html('Successfully updated ' + senddata['field'] + '.');
		$('#successToast').toast('show');
	};
};

function ingredientSave(index, newname, quantity) {
	var senddata = {
		'update' : 'ingredients',
		'index' : index,
		'name' : newname,
		'quantity' : quantity,
		'filename' : recipe_selected
	};
	$('#recipe_edit_ingredients_row').fadeOut(500).load('/recipedata', senddata).fadeIn(500);

	var senddata = {
		'refresh' : 'instructions',
		'filename' : recipe_selected
	};
	$('#recipe_edit_instructions_row').load('/recipedata', senddata);
};

function ingredientDelete(index) {
	var senddata = {
		'delete' : 'ingredients',
		'index' : index,
		'filename' : recipe_selected
	};
	$('#recipe_edit_ingredients_row').load('/recipedata', senddata);

	var senddata = {
		'refresh' : 'instructions',
		'filename' : recipe_selected
	};
	$('#recipe_edit_instructions_row').load('/recipedata', senddata);
};

function ingredientAdd() {
	var senddata = {
		'add' : 'ingredients',
		'filename' : recipe_selected
	};
	$('#recipe_edit_ingredients_row').load('/recipedata', senddata);

	var senddata = {
		'refresh' : 'instructions',
		'filename' : recipe_selected
	};
	$('#recipe_edit_instructions_row').load('/recipedata', senddata);
};

function instructionSave(index) {
	var text = $('#recipe_instructions_text_'+index).val();
	var step = $('#recipe_instructions_step_select_'+index).find(":selected").val();
	var ingredients = $('#recipe_instructions_ingredients_'+index).val();
	var senddata = {
		'update' : 'instructions',
		'index' : index, 
		'ingredients' : ingredients,
		'text' : text,
		'step' : step,
		'filename' : recipe_selected
	};
	$('#recipe_edit_instructions_row').fadeOut(500).load('/recipedata', senddata).fadeIn(500);
};

function instructionDelete(index) {
	var senddata = {
		'delete' : 'instructions',
		'index' : index,
		'filename' : recipe_selected
	};
	$('#recipe_edit_instructions_row').load('/recipedata', senddata);
};

function instructionAdd() {
	var senddata = {
		'add' : 'instructions',
		'filename' : recipe_selected
	};
	$('#recipe_edit_instructions_row').load('/recipedata', senddata);
};

function stepUpdate(index) {
	var mode = $('#recipe_step_mode_select_'+index).find(':selected').val();
	var pause = $('#recipe_step_switch_pause_'+index).is(':checked');
	var hold_temp = $('#recipe_step_hold_'+index).val();
	var notify = $('#recipe_step_switch_notify_'+index).is(':checked');
	var message = $('#recipe_step_notify_textarea_'+index).val();
	var primary = $('#recipe_step_trigger_temp_primary_'+index).val();
	var timer = $('#recipe_step_trigger_timer_'+index).val();
	//get all food probe trigger temps  
	var food = [];

	const collection = document.getElementsByClassName("recipeEditFoodTrigger_"+index);
	for (let i = 0; i < collection.length; i++) {
		var setting_id = collection[i].id;
		var setting_val = $('#'+setting_id).val();
		food[i] = setting_val;
	};

	var senddata = {
		'update' : 'steps',
		'index' : index, 
		'hold_temp' : hold_temp,
		'mode' : mode,
		'primary' : primary,
		'food' : food,
		'pause' : pause, 
		'notify' : notify, 
		'message' : message, 
		'timer' : timer,
		'filename' : recipe_selected
	};
	//console.log(senddata);
	$('#recipe_edit_steps_row').load('/recipedata', senddata);
}; 

function stepAdd(index) {
	var senddata = {
		'add' : 'steps',
		'index' : index,
		'filename' : recipe_selected
	};
	$('#recipe_edit_steps_row').load('/recipedata', senddata);
};

function stepDelete(index) {
	var senddata = {
		'delete' : 'steps',
		'index' : index,
		'filename' : recipe_selected
	};
	$('#recipe_edit_step_card_'+index).fadeOut(500);
	$('#recipe_edit_steps_row').load('/recipedata', senddata);
};

function recipeCheckState() {
    // Get control data and update control panel if needed
    $.ajax({
        url : '/api/control',
        type : 'GET',
        success : function (control) {
            // Relevant data returned from call:
            //  control.control.mode
			//  control.control.recipe.filename
			
			if (recipeMode != control.control.mode) {
				recipeMode = control.control.mode;
				if (recipeMode == 'Recipe') {
					var filename = control.control.recipe.filename;
					recipeRunStatus(filename);
					recipeRunStatusInterval = setInterval(function(){
						recipeRunStatus(filename);
					}, 4000);
				} else {
					recipeWelcome();
				};
			};
        }
    });
};

function recipeCheckStateStop() {
	clearInterval(recipeRunStatusInterval);
};

function recipeScrollToStep(step_num) {
	//$("#recipe_steps_step_card_{{ loop.index0 }}").get(0).scrollIntoView({behavior: 'smooth'});
	var id = 'recipe_steps_step_card_' + step_num;
	const yOffset = -50; 
	var element = document.getElementById(id);
	var y = element.getBoundingClientRect().top + window.pageYOffset + yOffset;

	window.scrollTo({top: y, behavior: 'smooth'});
};

function recipeDownloadFile(filename) {
	//console.log('Give me ' + filename);
	window.location = '/recipedata/download/' + filename;
};

	// === Document Ready ===

$(document).ready(function(){
	recipeCheckState();
}); // End of Document Ready Function 
