import datetime
from flask import render_template, request
from common.common import read_settings, read_control, read_pellet_db, write_pellet_db, write_control, backup_pellet_db

from . import pellets_bp

@pellets_bp.route('/<action>', methods=['POST','GET'])
@pellets_bp.route('/', methods=['POST','GET'])
def pellets_page(action=None):
    settings = read_settings()
    pelletdb = read_pellet_db()
    control = read_control()

    event = {
        'type' : 'none',
        'text' : ''
    }

    if request.method == 'POST' and action == 'loadprofile':
        response = request.form
        if 'load_profile' in response:
            if response['load_profile'] == 'true':
                pelletdb['current']['pelletid'] = response['load_id']
                pelletdb['current']['est_usage'] = 0
                control = read_control()
                control['hopper_check'] = True
                write_control(control, origin='app')
                now = str(datetime.datetime.now())
                now = now[0:19] # Truncate the microseconds
                pelletdb['current']['date_loaded'] = now 
                pelletdb['log'][now] = response['load_id']
                write_pellet_db(pelletdb)
                event['type'] = 'updated'
                event['text'] = 'Successfully loaded profile and logged.'
                backup_pellet_db(action='backup')
    elif request.method == 'GET' and action == 'hopperlevel':
        control = {}
        control['hopper_check'] = True
        write_control(control, origin='app')
    elif request.method == 'POST' and action == 'editbrands':
        response = request.form
        if 'delBrand' in response:
            del_brand = response['delBrand']
            if del_brand in pelletdb['brands']:
                pelletdb['brands'].remove(del_brand)
                write_pellet_db(pelletdb)
                event['type'] = 'updated'
                event['text'] = del_brand + ' successfully deleted.'
            else: 
                event['type'] = 'error'
                event['text'] = del_brand + ' not found in pellet brands.'
        elif 'newBrand' in response:
            new_brand = response['newBrand']
            if(new_brand in pelletdb['brands']):
                event['type'] = 'error'
                event['text'] = new_brand + ' already in pellet brands list.'
            else: 
                pelletdb['brands'].append(new_brand)
                write_pellet_db(pelletdb)
                event['type'] = 'updated'
                event['text'] = new_brand + ' successfully added.'

    elif request.method == 'POST' and action == 'editwoods':
        response = request.form
        if 'delWood' in response:
            del_wood = response['delWood']
            if del_wood in pelletdb['woods']:
                pelletdb['woods'].remove(del_wood)
                write_pellet_db(pelletdb)
                event['type'] = 'updated'
                event['text'] = del_wood + ' successfully deleted.'
            else: 
                event['type'] = 'error'
                event['text'] = del_wood + ' not found in pellet wood list.'
        elif 'newWood' in response:
            new_wood = response['newWood']
            if(new_wood in pelletdb['woods']):
                event['type'] = 'error'
                event['text'] = new_wood + ' already in pellet wood list.'
            else: 
                pelletdb['woods'].append(new_wood)
                write_pellet_db(pelletdb)
                event['type'] = 'updated'
                event['text'] = new_wood + ' successfully added.'

    elif request.method == 'POST' and action == 'addprofile':
        response = request.form
        if 'addprofile' in response:
            profile_id = ''.join(filter(str.isalnum, str(datetime.datetime.now())))

            pelletdb['archive'][profile_id] = {
                'id' : profile_id,
                'brand' : response['brand_name'],
                'wood' : response['wood_type'],
                'rating' : int(response['rating']),
                'comments' : response['comments']
            }
            event['type'] = 'updated'
            event['text'] = 'Successfully added profile to database.'

            if response['addprofile'] == 'add_load':
                pelletdb['current']['pelletid'] = profile_id
                control = {}
                control['hopper_check'] = True
                write_control(control, origin='app')
                now = str(datetime.datetime.now())
                now = now[0:19] # Truncate the microseconds
                pelletdb['current']['date_loaded'] = now
                pelletdb['current']['est_usage'] = 0
                pelletdb['log'][now] = profile_id
                event['text'] = 'Successfully added profile and loaded.'

            write_pellet_db(pelletdb)

    elif request.method == 'POST' and action == 'editprofile':
        response = request.form
        if 'editprofile' in response:
            profile_id = response['editprofile']
            pelletdb['archive'][profile_id]['brand'] = response['brand_name']
            pelletdb['archive'][profile_id]['wood'] = response['wood_type']
            pelletdb['archive'][profile_id]['rating'] = int(response['rating'])
            pelletdb['archive'][profile_id]['comments'] = response['comments']
            write_pellet_db(pelletdb)
            event['type'] = 'updated'
            event['text'] = 'Successfully updated ' + response['brand_name'] + ' ' + response['wood_type'] + \
                            ' profile in database.'
        elif 'delete' in response:
            profile_id = response['delete']
            if pelletdb['current']['pelletid'] == profile_id:
                event['type'] = 'error'
                event['text'] = 'Error: ' + response['brand_name'] + ' ' + response['wood_type'] + \
                                ' profile cannot be deleted if it is currently loaded.'
            else: 
                pelletdb['archive'].pop(profile_id) # Remove the profile from the archive
                for index in pelletdb['log']:  # Remove this profile ID for the logs
                    if(pelletdb['log'][index] == profile_id):
                        pelletdb['log'][index] = 'deleted'
                write_pellet_db(pelletdb)
                event['type'] = 'updated'
                event['text'] = 'Successfully deleted ' + response['brand_name'] + ' ' + response['wood_type'] + \
                                ' profile in database.'

    elif request.method == 'POST' and action == 'deletelog':
        response = request.form
        if 'delLog' in response:
            del_log = response['delLog']
            if del_log in pelletdb['log']:
                pelletdb['log'].pop(del_log)
                write_pellet_db(pelletdb)
                event['type'] = 'updated'
                event['text'] = 'Log successfully deleted.'
            else:
                event['type'] = 'error'
                event['text'] = 'Item not found in pellet log.'

    grams = pelletdb['current']['est_usage']
    pounds = round(grams * 0.00220462, 2)
    ounces = round(grams * 0.03527392, 2)
    est_usage_imperial = f'{pounds} lbs' if pounds > 1 else f'{ounces} ozs'
    est_usage_metric = f'{round(grams, 2)} g' if grams < 1000 else f'{round(grams / 1000, 2)} kg'

    return render_template('pellets/index.html',
                            alert=event,
                            pelletdb=pelletdb,
                            est_usage_imperial=est_usage_imperial,
                            est_usage_metric=est_usage_metric,
                            settings=settings,
                            control=control,
                            units=settings['globals']['units'],
                            page_theme=settings['globals'].get('page_theme', 'light'),
                            grill_name=settings['globals'].get('grill_name', '')
                            )

