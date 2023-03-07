#!/usr/bin/env python3
'''
PiFire - File / Media Functions
===============================

This file contains functions for file media manipulations for the common file formats (i.e. Cookfile and Recipe Files). 
'''

'''
Imported Modules
================
'''
import os
import zipfile
from common import generate_uuid
from file_mgmt.common import update_json_file_data, read_json_file_data
from PIL import Image, ExifTags


'''
Functions
=========
'''

def add_asset(filename, assetpath, assetfile):
    assetsjson, status = read_json_file_data(filename, 'assets')
	#  Guess the filetype
    filetype = assetfile.rsplit('.', 1)[1].lower()
	#  Create new asset ID
    asset_id = generate_uuid()
	#  Create new asset structure
    newasset = {
			'id' : asset_id,
			'filename' : asset_id + f'.{filetype}',
			'type' : filetype
		}
	
    if status == 'OK':
		#  Append the new asset information to the file
        assetsjson.append(newasset)
		#  Update cookfile with new asset information
        update_json_file_data(assetsjson, filename, 'assets')
		#  Rename asset file to [asset_id].[filetype]
        fullsize = f'{assetpath}/{asset_id}.{filetype}'
        os.rename(os.path.join(assetpath, assetfile), fullsize)

		#  Rotate image if needed
        _rotate_image(assetpath, asset_id, filetype)

		#  Create a thumbnail from the image
        thumbpathname, status = _create_thumbnail(assetpath, asset_id, filetype)

		#  Resize original image
        status = _resize_image(assetpath, asset_id, filetype, max_size=(800, 600))

		#  Add the files to the zipfile
        with zipfile.ZipFile(filename, 'a') as archive:
            if status=='OK':
                archive.write(thumbpathname, arcname=f'assets/thumbs/{asset_id}.{filetype}')
            archive.write(fullsize, arcname=f'assets/{asset_id}.{filetype}')
    else: 
        print(f'status: {status}')

    return(asset_id, filetype)

def _rotate_image(filepath, asset_id, filetype):
	status = 'OK'
	'''
		Rotates the image if necessary.	
	'''

	try:
		#  Load image into memory
		imagefile = f'{filepath}/{asset_id}.{filetype}'
		image = Image.open(imagefile)

		for orientation in ExifTags.TAGS.keys():
			if ExifTags.TAGS[orientation]=='Orientation':
				break
		
		exif = image._getexif()

		if(exif is not None):
			rotate = True
			if exif[orientation] == 3:
				image=image.rotate(180, expand=True)
			elif exif[orientation] == 6:
				image=image.rotate(270, expand=True)
			elif exif[orientation] == 8:
				image=image.rotate(90, expand=True)
			else:
				rotate=False
			
			if rotate:
				image.save(imagefile)
		
		image.close()
	
	except (AttributeError, KeyError, IndexError):
		status = 'ERROR: Rotation Failed.'
	except:
		status = 'ERROR: Rotation Failed, Unspecified Error.'

	return status

def _create_thumbnail(filepath, asset_id, filetype, crop=True):
	status = 'OK'
	#  Import PIL for image manipulations
	from PIL import Image
	#  Load image into memory
	imagefile = f'{filepath}/{asset_id}.{filetype}'
	image = Image.open(imagefile)
	width, height = image.size

	#  Crop Image 
	if crop:
		if width > height:
			image = image.crop((width//2 - height//2, 0, width//2 + height//2, height))
		elif height > width:
			image = image.crop((0, height//2 - width//2, width, height//2 + width//2))
		#  Get new width & height
		width, height = image.size

	#  Resize Image to 128px x 128px unless it's already the right size
	if (width != 128) and (height != 128):
		image = image.resize((128, 128))

	#  Save thumb image in filepath + /thumbs
	if not os.path.exists(f'{filepath}/thumbs'):
		os.mkdir(f'{filepath}/thumbs')
	thumbpathname = f'{filepath}/thumbs/{asset_id}.{filetype}'
	image.save(thumbpathname)

	return(thumbpathname, status)

def _resize_image(assetpath, asset_id, filetype, max_size=(800, 600)):
	status = 'OK'
	#  Import PIL for image manipulations
	from PIL import Image, ImageOps
	#  Load image into memory
	imagefile = f'{assetpath}/{asset_id}.{filetype}'
	image = Image.open(imagefile)
	#  Resizes image to fit into max_size and maintains aspect ratio
	image = ImageOps.contain(image, max_size)
	#  Saves the image file
	image.save(imagefile)

	return(status)

def set_thumbnail(filename, thumbfilename):
	'''
	filename = name of the cookfile that is being edited
	thumbfilename = filename of the thumbnail image which is being set
		without the assets/thumbs/ folder in the path 
	'''
	metadata, status = read_json_file_data(filename, 'metadata')
	if status=='OK':
		metadata['thumbnail'] = f'{thumbfilename}'
		update_json_file_data(metadata, filename, 'metadata')

def unpack_thumb(thumbname, filename):
	try:
		with zipfile.ZipFile(filename, mode="r") as archive:
			thumb = archive.read(f'assets/thumbs/{thumbname}')  # Read bytes into variable
			tmp_id = generate_uuid()

			if not os.path.exists(f'/tmp/pifire'):
				os.mkdir(f'/tmp/pifire')

			if not os.path.exists(f'/tmp/pifire/{tmp_id}'):
				os.mkdir(f'/tmp/pifire/{tmp_id}')

			#  Write fullsize image to disk
			destination = open(f'/tmp/pifire/{tmp_id}/{thumbname}', "wb")  # Write bytes to proper destination
			destination.write(thumb)
			destination.close()
			path_filename = f'{tmp_id}/{thumbname}'

			#  Create temporary folder for the thumbnail
			if not os.path.exists('./static/img/tmp'):
				os.mkdir(f'./static/img/tmp')
			if not os.path.exists(f'./static/img/tmp/{tmp_id}'):
				os.symlink(f'/tmp/pifire/{tmp_id}', f'./static/img/tmp/{tmp_id}')

	except:
		path_filename = ''
	
	return path_filename 
