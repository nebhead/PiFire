from flask import render_template, make_response
from . import manifest_bp

'''
Manifest Route for Web Application Integration
'''
@manifest_bp.route('/')
def manifest():
	res = make_response(render_template('manifest/manifest.json'), 200)
	res.headers["Content-Type"] = "text/cache-manifest"
	return res
