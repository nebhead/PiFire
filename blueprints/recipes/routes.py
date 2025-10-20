import os
from werkzeug.utils import secure_filename
from flask import render_template, request, current_app, send_file, jsonify, render_template_string
from common.common import read_settings, read_control
from common.app import paginate_list, allowed_file
from file_mgmt.common import update_json_file_data, remove_assets
from file_mgmt.media import add_asset
from file_mgmt.recipes import read_recipefile, create_recipefile, get_recipefilelist, get_recipefilelist_details

from . import recipes_bp

@recipes_bp.route('/', methods=['POST','GET'])
def recipes_page():
    settings = read_settings()
    control = read_control()
    return render_template('recipes/index.html',
                            settings=settings,
                            control=control,
                            page_theme=settings['globals']['page_theme'],
                            grill_name=settings['globals']['grill_name'])

@recipes_bp.route('/data', methods=['POST', 'GET'])
@recipes_bp.route('/data/upload', methods=['POST', 'GET'])
@recipes_bp.route('/data/download/<filename>', methods=['GET'])
def recipes_data(filename=None):
    settings = read_settings()
    control = read_control()
    RECIPE_FOLDER = current_app.config['RECIPE_FOLDER']

    if(request.method == 'GET') and (filename is not None):
        filepath = f'{RECIPE_FOLDER}{filename}'
        #print(f'Sending: {filepath}')
        return send_file(filepath, as_attachment=True, max_age=0)

    if(request.method == 'POST') and ('form' in request.content_type):
        requestform = request.form
        #print(f'Request FORM: {requestform}')
        if('upload' in requestform):
            #print(f'Files: {request.files}')
            remote_file = request.files['recipefile']
            result = "error"
            if remote_file.filename != '':
                if remote_file and allowed_file(remote_file.filename):
                    filename = secure_filename(remote_file.filename)
                    remote_file.save(os.path.join(RECIPE_FOLDER, filename))
                    result = "success"
            return jsonify({ 'result' : result})
        if('uploadassets' in requestform):
            # Assume we have request.files and localfile in response
            uploadedfiles = request.files.getlist('assetfiles')
            filename = requestform['filename']
            filepath = f'{RECIPE_FOLDER}{filename}'

            errors = []
            for remotefile in uploadedfiles:
                if (remotefile.filename != ''):
                    # Load the Recipe File 
                    recipe_data, status = read_recipefile(filepath)
                    parent_id = recipe_data['metadata']['id']
                    tmp_path = f'/tmp/pifire/{parent_id}'
                    if not os.path.exists(tmp_path):
                        os.mkdir(tmp_path)

                    if remotefile and allowed_file(remotefile.filename):
                        asset_filename = secure_filename(remotefile.filename)
                        pathfile = os.path.join(tmp_path, asset_filename)
                        remotefile.save(pathfile)
                        add_asset(filepath, tmp_path, asset_filename)
                    else:
                        errors.append('Disallowed File Upload.')
            if len(errors):
                status = 'error'
            else:
                status = 'success'
            return jsonify({ 'result' : status, 'errors' : errors})
        if('recipefilelist' in requestform):
            page = int(requestform['page'])
            reverse = True if requestform['reverse'] == 'true' else False
            itemsperpage = int(requestform['itemsperpage'])
            filelist = get_recipefilelist()
            recipefilelist = []
            for filename in filelist:
                recipefilelist.append({'filename' : filename, 'title' : '', 'thumbnail' : ''})
            paginated_recipefile = paginate_list(recipefilelist, 'filename', reverse, itemsperpage, page)
            paginated_recipefile['displaydata'] = get_recipefilelist_details(paginated_recipefile['displaydata'])
            return render_template('recipes/_recipefile_list.html', pgntdrf = paginated_recipefile)
        if('recipeview' in requestform):
            filename = requestform['filename']
            filepath = f'{RECIPE_FOLDER}{filename}'
            recipe_data, status = read_recipefile(filepath)
            return render_template('recipes/_recipe_view.html', recipe_data=recipe_data, recipe_filename=filename, recipe_filepath=filepath)
        if('recipeedit' in requestform):
            filename = requestform['filename']
            if filename == '':
                filepath = create_recipefile()
                filename = filepath.replace(RECIPE_FOLDER, '')
            else: 
                filepath = f'{RECIPE_FOLDER}{filename}'
            recipe_data, status = read_recipefile(filepath)
            return render_template('recipes/_recipe_edit.html', recipe_data=recipe_data, recipe_filename=filename, recipe_filepath=filepath)
        if('update' in requestform):
            filename = requestform['filename']
            filepath = f'{RECIPE_FOLDER}{filename}'
            recipe_data, status = read_recipefile(filepath)
            if requestform['update'] in ['metadata']:
                field = requestform['field']
                if field in ['prep_time', 'cook_time', 'rating']:
                    recipe_data['metadata'][field] = int(requestform['value'])
                elif field == 'food_probes':
                    food_probes = int(requestform['value'])
                    recipe_data['metadata'][field] = food_probes 
                    for index, step in enumerate(recipe_data['recipe']['steps']):
                        while len(step['trigger_temps']['food']) > food_probes:
                            recipe_data['recipe']['steps'][index]['trigger_temps']['food'].pop()
                        while len(step['trigger_temps']['food']) < food_probes:
                            recipe_data['recipe']['steps'][index]['trigger_temps']['food'].append(0)
                    update_json_file_data(recipe_data['recipe'], filepath, 'recipe')
                else:	
                    recipe_data['metadata'][field] = requestform['value']
                update_json_file_data(recipe_data['metadata'], filepath, 'metadata')
                if field == 'title': 
                    render_string = "{% from 'recipes/_macro_recipes.html' import render_recipe_edit_title %}{{ render_recipe_edit_title(recipe_data, recipe_filename) }}"
                elif field == 'description':
                    render_string = "{% from 'recipes/_macro_recipes.html' import render_recipe_edit_description %}{{ render_recipe_edit_description(recipe_data) }}"
                else:
                    render_string = "{% from 'recipes/_macro_recipes.html' import render_recipe_edit_metadata %}{{ render_recipe_edit_metadata(recipe_data) }}"
                return render_template_string(render_string, recipe_data=recipe_data, recipe_filename=filename)
            elif requestform['update'] == 'ingredients':
                recipe = recipe_data['recipe']
                ingredient_index = int(requestform['index'])
                if recipe['ingredients'][ingredient_index]['name'] != requestform['name']:
                    # Go Fixup any Instruction Step that includes this Ingredient First
                    for index, direction in enumerate(recipe['instructions']):
                        if recipe['ingredients'][ingredient_index]['name'] in recipe['instructions'][index]['ingredients']:
                            recipe['instructions'][index]['ingredients'].remove(recipe['ingredients'][ingredient_index]['name'])
                            recipe['instructions'][index]['ingredients'].append(requestform['name'])
                recipe['ingredients'][ingredient_index]['name'] = requestform['name']
                recipe['ingredients'][ingredient_index]['quantity'] = requestform['quantity']
                recipe_data['recipe'] = recipe 
                update_json_file_data(recipe, filepath, 'recipe')
                render_string = "{% from 'recipes/_macro_recipes.html' import render_recipe_edit_ingredients %}{{ render_recipe_edit_ingredients(recipe_data) }}"
                return render_template_string(render_string, recipe_data=recipe_data)
            elif requestform['update'] == 'instructions':
                instruction_index = int(requestform['index'])
                if 'ingredients[]' in requestform:
                    ingredients = request.form.getlist('ingredients[]')
                else:
                    ingredients = []
                recipe_data['recipe']['instructions'][instruction_index]['ingredients'] = ingredients 
                recipe_data['recipe']['instructions'][instruction_index]['text'] = requestform['text']
                recipe_data['recipe']['instructions'][instruction_index]['step'] = int(requestform['step'])
                update_json_file_data(recipe_data['recipe'], filepath, 'recipe')
                render_string = "{% from 'recipes/_macro_recipes.html' import render_recipe_edit_instructions %}{{ render_recipe_edit_instructions(recipe_data) }}"
                return render_template_string(render_string, recipe_data=recipe_data)
            elif requestform['update'] == 'steps':
                step_index = int(requestform['index'])
                food = request.form.getlist('food[]')
                for i in range(0, len(food)):
                    food[i] = int(food[i])
                recipe_data['recipe']['steps'][step_index]['hold_temp'] = int(requestform['hold_temp'])
                recipe_data['recipe']['steps'][step_index]['timer'] = int(requestform['timer'])
                recipe_data['recipe']['steps'][step_index]['mode'] = requestform['mode']
                recipe_data['recipe']['steps'][step_index]['trigger_temps']['primary'] = int(requestform['primary'])
                recipe_data['recipe']['steps'][step_index]['trigger_temps']['food'] = food
                recipe_data['recipe']['steps'][step_index]['pause'] = True if requestform['pause'] == 'true' else False 
                recipe_data['recipe']['steps'][step_index]['notify'] = True if requestform['notify']== 'true' else False 
                recipe_data['recipe']['steps'][step_index]['message'] = requestform['message']

                update_json_file_data(recipe_data['recipe'], filepath, 'recipe')
                render_string = "{% from 'recipes/_macro_recipes.html' import render_recipe_edit_steps %}{{ render_recipe_edit_steps(recipe_data) }}"
                return render_template_string(render_string, recipe_data=recipe_data)
            else:
                return '<strong color="red">No Data</strong>'
        if('delete' in requestform):
            filename = requestform['filename']
            filepath = f'{RECIPE_FOLDER}{filename}'
            recipe_data, status = read_recipefile(filepath)
            if requestform['delete'] == 'ingredients':
                recipe = recipe_data['recipe']
                ingredient_index = int(requestform['index'])
                # Go Fixup any Instruction Step that includes this Ingredient First
                for index, direction in enumerate(recipe['instructions']):
                    if recipe['ingredients'][ingredient_index]['name'] in recipe['instructions'][index]['ingredients']:
                        recipe['instructions'][index]['ingredients'].remove(recipe['ingredients'][ingredient_index]['name'])
                recipe['ingredients'].pop(ingredient_index)
                recipe_data['recipe'] = recipe 
                update_json_file_data(recipe, filepath, 'recipe')
                render_string = "{% from 'recipes/_macro_recipes.html' import render_recipe_edit_ingredients %}{{ render_recipe_edit_ingredients(recipe_data) }}"
                return render_template_string(render_string, recipe_data=recipe_data)
            elif requestform['delete'] == 'instructions':
                instruction_index = int(requestform['index'])
                recipe_data['recipe']['instructions'].pop(instruction_index)
                update_json_file_data(recipe_data['recipe'], filepath, 'recipe')
                render_string = "{% from 'recipes/_macro_recipes.html' import render_recipe_edit_instructions %}{{ render_recipe_edit_instructions(recipe_data) }}"
                return render_template_string(render_string, recipe_data=recipe_data)
            elif requestform['delete'] == 'steps':
                step_index = int(requestform['index'])
                recipe_data['recipe']['steps'].pop(step_index)
                update_json_file_data(recipe_data['recipe'], filepath, 'recipe')
                render_string = "{% from 'recipes/_macro_recipes.html' import render_recipe_edit_steps %}{{ render_recipe_edit_steps(recipe_data) }}"
                return render_template_string(render_string, recipe_data=recipe_data)
            else:
                return '<strong color="red">No Data</strong>'
        if('add' in requestform):
            filename = requestform['filename']
            filepath = f'{RECIPE_FOLDER}{filename}'
            recipe_data, status = read_recipefile(filepath)
            if requestform['add'] == 'ingredients':
                new_ingredient = {
                    "name" : "",
                    "quantity" : "",
                    "assets" : []
                }
                recipe_data['recipe']['ingredients'].append(new_ingredient)
                update_json_file_data(recipe_data['recipe'], filepath, 'recipe')
                render_string = "{% from 'recipes/_macro_recipes.html' import render_recipe_edit_ingredients %}{{ render_recipe_edit_ingredients(recipe_data) }}"
                return render_template_string(render_string, recipe_data=recipe_data)
            elif requestform['add'] == 'instructions': 
                new_instruction = {
                    "text" : "",
                    "ingredients" : [],
                    "assets" : [],
                    "step" : 0
                }
                recipe_data['recipe']['instructions'].append(new_instruction)
                update_json_file_data(recipe_data['recipe'], filepath, 'recipe')
                render_string = "{% from 'recipes/_macro_recipes.html' import render_recipe_edit_instructions %}{{ render_recipe_edit_instructions(recipe_data) }}"
                return render_template_string(render_string, recipe_data=recipe_data)
            elif requestform['add'] == 'steps':
                step_index = int(requestform['index'])
                food_list = []
                for count in range(0, recipe_data['metadata']['food_probes']):
                    food_list.append(0)
                new_step = {
                    "hold_temp": 0,
                    "message": "",
                    "mode": "Smoke",
                    "notify": False,
                    "pause": False,
                    "timer": 0,
                    "trigger_temps": {
                        "primary": 0,
                        "food": food_list,
                    }
                }
                recipe_data['recipe']['steps'].insert(step_index, new_step)
                update_json_file_data(recipe_data['recipe'], filepath, 'recipe')
                render_string = "{% from 'recipes/_macro_recipes.html' import render_recipe_edit_steps %}{{ render_recipe_edit_steps(recipe_data) }}"
                return render_template_string(render_string, recipe_data=recipe_data)
            else:
                return '<strong color="red">No Data</strong>'
        if('refresh' in requestform):
            filename = requestform['filename']
            filepath = f'{RECIPE_FOLDER}{filename}'
            recipe_data, status = read_recipefile(filepath)
            if requestform['refresh'] == 'metadata':
                render_string = "{% from 'recipes/_macro_recipes.html' import render_recipe_edit_metadata %}{{ render_recipe_edit_metadata(recipe_data) }}"
                return render_template_string(render_string, recipe_data=recipe_data)
            if requestform['refresh'] == 'description':
                render_string = "{% from 'recipes/_macro_recipes.html' import render_recipe_edit_description %}{{ render_recipe_edit_description(recipe_data) }}"
                return render_template_string(render_string, recipe_data=recipe_data)
            if requestform['refresh'] == 'ingredients':
                render_string = "{% from 'recipes/_macro_recipes.html' import render_recipe_edit_ingredients %}{{ render_recipe_edit_ingredients(recipe_data) }}"
                return render_template_string(render_string, recipe_data=recipe_data)
            if requestform['refresh'] == 'instructions':
                render_string = "{% from 'recipes/_macro_recipes.html' import render_recipe_edit_instructions %}{{ render_recipe_edit_instructions(recipe_data) }}"
                return render_template_string(render_string, recipe_data=recipe_data)
            if requestform['refresh'] == 'steps':
                render_string = "{% from 'recipes/_macro_recipes.html' import render_recipe_edit_steps %}{{ render_recipe_edit_steps(recipe_data) }}"
                return render_template_string(render_string, recipe_data=recipe_data)
        if('reciperunstatus' in requestform):
            control = read_control()
            if control['mode'] != 'Recipe':
                filename = requestform['filename']
                filepath = f'{RECIPE_FOLDER}{filename}'
            else: 
                filepath = control['recipe']['filename']
                filename = filepath.replace(RECIPE_FOLDER, '')

            recipe_data, status = read_recipefile(filepath)
            return render_template('recipes/_recipe_status.html', control=control, recipe_data=recipe_data, recipe_filename=filename, recipe_filepath=filepath)
        if('recipeassetmanager' in requestform):
            filename = requestform['filename']
            filepath = f'{RECIPE_FOLDER}{filename}'
            recipe_data, status = read_recipefile(filepath)
            section = requestform['section']
            section_index = int(requestform['index'])
            if section == 'splash':
                assets_selected = [recipe_data['metadata']['image']]
            elif section in ['ingredients', 'instructions']: 
                assets_selected = recipe_data['recipe'][section][section_index]['assets']
            elif section == 'comments': 
                assets_selected = recipe_data['comments'][section_index]['assets']
            else:
                assets_selected = []
            return render_template('recipes/_recipe_assets.html', recipe_data=recipe_data, recipe_filename=filename, recipe_filepath=filepath, section=section, section_index=section_index, selected=assets_selected)

        if('recipeshowasset' in requestform):
            filename = requestform['filename']
            filepath = f'{RECIPE_FOLDER}{filename}'
            recipe_data, status = read_recipefile(filepath)
            section = requestform['section']
            section_index = int(requestform['section_index'])
            selected_asset = requestform['asset']
            if(section == 'metadata'):
                assets = [recipe_data['metadata']['title']]
            else:
                assets = recipe_data['recipe'][section][section_index]['assets']
            recipe_id = recipe_data['metadata']['id']
            render_string = "{% from 'recipes/_macro_recipes.html' import render_recipe_asset_viewer %}{{ render_recipe_asset_viewer(assets, recipe_id, selected_asset) }}"
            return render_template_string(render_string, assets=assets, recipe_id=recipe_id, selected_asset=selected_asset)

    ''' AJAX POST JSON Type Method Handler '''
    if(request.method == 'POST') and ('json' in request.content_type): 
        requestjson = request.json
        #print(f'Request JSON: {requestjson}')
        if('deletefile' in requestjson): 
            filename = requestjson['filename']
            filepath = f'{RECIPE_FOLDER}{filename}'
            os.system(f'rm {filepath}')
            return jsonify({'result' : 'success'})
        if('assetchange' in requestjson):
            filename = requestjson['filename']
            filepath = f'{RECIPE_FOLDER}{filename}'
            recipe_data, status = read_recipefile(filepath)
            section = requestjson['section']
            section_index = requestjson['index']
            asset_name = requestjson['asset_name']
            asset_id = requestjson['asset_id']
            action = requestjson['action']
            if(action == 'add'):
                if(section in ['ingredients', 'instructions']):
                    if asset_name not in recipe_data['recipe'][section][section_index]['assets']:
                        recipe_data['recipe'][section][section_index]['assets'].append(asset_name)
                        update_json_file_data(recipe_data['recipe'], filepath, 'recipe')
                elif(section in ['splash']):
                    recipe_data['metadata']['image'] = asset_name
                    recipe_data['metadata']['thumbnail'] = asset_name 
                    update_json_file_data(recipe_data['metadata'], filepath, 'metadata')
                elif(section in ['delete']):
                    remove_assets(filepath, [asset_name], filetype='recipefile')
            elif(action == 'remove'):
                if(section in ['ingredients', 'instructions']):
                    if asset_name in recipe_data['recipe'][section][section_index]['assets']:
                        recipe_data['recipe'][section][section_index]['assets'].remove(asset_name)
                        update_json_file_data(recipe_data['recipe'], filepath, 'recipe')
                elif(section in ['splash']):
                    recipe_data['metadata']['image'] = ''
                    recipe_data['metadata']['thumbnail'] = ''
                    update_json_file_data(recipe_data['metadata'], filepath, 'metadata')
                elif(section in ['delete']):
                    remove_assets(filepath, [asset_name], filetype='recipefile')
            return jsonify({'result' : 'success'})

    return jsonify({'result' : 'error'})
