import os
import sys
import json

from flask import Blueprint, request

from agpb.main.utils import get_category_data, get_language_data

main = Blueprint('main', __name__)

@main.route('/')
def home():
    return '<h2> Welcome to African German Phrasebook Server</h2>'

@main.route('/api/v1/categories')
def getCategories():
    '''
    Get application categories
    '''

    # section_name = request.args.get('section')
    category_data = get_category_data()
    if category_data:
        return category_data
    else:
        return '<h2> Unable to get Category data at the moment</h2>'

@main.route('/api/v1/languages')
def getLanguages():
    '''
    Get application categories
    '''

    # section_name = request.args.get('section')
    language_data = get_language_data()
    if language_data:
        return language_data
    else:
        return '<h2> Unable to get Category data at the moment</h2>'
