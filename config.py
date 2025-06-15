''' This file contains configuration settings for the application. '''

import os

class Config:
	BACKUP_PATH = './backups/'  # Path to backups of settings.json, pelletdb.json
	UPLOAD_FOLDER = BACKUP_PATH  # Point uploads to the backup path
	HISTORY_FOLDER = './history/'  # Path to historical cook files
	RECIPE_FOLDER = './recipes/'  # Path to recipe files 
	LOGS_FOLDER = './logs/'  # Path to log files 
	ALLOWED_EXTENSIONS = {'json', 'pifire', 'pfrecipe', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'log'}

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False