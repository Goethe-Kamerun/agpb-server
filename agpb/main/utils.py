import os
import shutil
import sys
import uuid
import json
import ast
import io
import requests
import traceback
from sqlalchemy.sql import text
from agpb import app, db
from flask import send_file, abort, Response, jsonify
from requests_oauthlib import OAuth1
from wikibase_api import Wikibase
from agpb.models import Category, Language, Text


def commit_changes_to_db():
    '''
    Test for the success of a database commit operation.

    '''
    try:
        db.session.commit()
        return True
    except Exception:
        # TODO: We could add a try catch here for the error
        print('Exception when committing to database.', file=sys.stderr)
        traceback.print_stack()
        traceback.print_exc()
        db.session.rollback()
        # for resetting non-commited .add()
        db.session.flush()
    return False


def get_category_data():
    categories_data = {}
    category_data = []
    categories = Category.query.all()
    if categories is not None:
        for category in categories:
            category_data_entry = {}
            category_data_entry['id'] = category.id
            category_data_entry['label'] = category.label
            category_data.append(category_data_entry)
        categories_data['categories'] = category_data
    return categories_data


def build_country_lang_code(lang_code):
    country_ext = 'cm'
    if lang_code == 'de':
        country_ext = 'de'
    return country_ext + '_' + lang_code


def build_lang_url(lang_code, url_type):
    country_ext = 'cm'
    ip_address = app.config['SERVER_ADDRESS']
    api_route = '/api/v1/translations?lang_code='

    if lang_code == 'de':
        country_ext = 'de'

    url = ip_address + api_route + country_ext + '_' + lang_code
    if url_type == 'zip':
        url += '&return_type=zip'
    else:
        url += '&return_type=json'
    return url


def check_lang_support(lang_code):
    root_dir = './agpb/db/data/trans/'
    lang_dirs = os.listdir(root_dir)
    if lang_code in lang_dirs:
        return 'true'
    else:
        return 'false'


def get_language_data():
    languages_data = {}
    language_data = []
    languages = Language.query.all()
    if languages is not None:
        for language in languages:
            language_data_entry = {}
            language_data_entry['name'] = language.label
            language_data_entry['lang_code'] = build_country_lang_code(language.lang_code)
            language_data_entry['zip_url'] = build_lang_url(language.lang_code, 'zip')
            language_data_entry['json_url'] = build_lang_url(language.lang_code, 'json')
            language_data_entry['supported'] = check_lang_support(build_country_lang_code(
                                                                  language.lang_code))
            language_data.append(language_data_entry)
        languages_data['data'] = language_data
    return languages_data


def make_audio_id(translation_id, lang_code):
    country_ext = 'cm'

    if lang_code == 'de':
        country_ext = 'de'

    if translation_id < 10:
        return country_ext + '_' + lang_code + '_00' + str(translation_id) + '.mp3'
    elif translation_id >= 10 and translation_id <= 99:
        return country_ext + '_' + lang_code + '_0' + str(translation_id) + '.mp3'
    else:
        return country_ext + '_' + lang_code + '_' + str(translation_id) + '.mp3'


def create_translation_text_file(trans_text, lang_code):
    country_ext = 'cm'

    if lang_code == 'de':
        country_ext = 'de'
    root_dir = './agpb/db/data/trans/' + country_ext + '_' + lang_code
    file_name = root_dir + '/' + country_ext + '_' + lang_code + '.json'

    # Remove old file in case of update
    if os.path.isfile(file_name):
        os.remove(file_name)

    with open(file_name, 'a') as file:
        file.write(trans_text.strip())

    return root_dir


def create_zip_file(directory, lang_code):
    archived_file = shutil.make_archive(directory, 'zip', directory)
    return archived_file


def convert_encoded_text(text):
    # norm_data = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore')
    return text


def get_audio_file_path(audio):
    country_code = audio.split('_')[0] + '_' + audio.split('_')[1]
    audio_full_path = app.config['SERVER_ADDRESS'] + \
        app.config['PLAY_AUDIO_ROUTE'] + 'lang=' + \
        country_code + '&file=' + audio
    return audio_full_path


def get_audio_file(lang_code, audio_number):
    download_directory = app.config['UPLOADS_DIR'] + \
        lang_code + '/' + audio_number
    return send_file(download_directory, as_attachment=True)


def get_translation_data(language_code, return_type):
    translations = []
    language = Language.query.filter_by(lang_code=language_code).first()
    # category_id = Category.query.filter_by(id=category_number).first().id
    texts = Text.query.filter_by(language_id=language.id).all()

    # filter text in particular language
    for text in texts:
        translation_entry = {}
        translation_entry['No'] = str(text.translation_id)
        translation_entry['text'] = convert_encoded_text(text.label)
        if text.category_id is None:
            translation_entry['category'] = 'none'
        else:
            translation_entry['category'] = Category.query.filter_by(id=text.category_id).first().label
        translation_entry['audio'] = make_audio_id(text.translation_id,
                                                   language.lang_code)
        translations.append(translation_entry)

    # translation_data['export default'] = translations
    translations = json.dumps(translations)
    if return_type == 'json':
        translations = ast.literal_eval(translations)
        for translation in translations:
            translation['audio'] = get_audio_file_path(translation['audio'])

        return json.dumps(translations, ensure_ascii=False).encode('utf8')
    elif return_type == 'zip':
        trans_directory = create_translation_text_file(translations, language.lang_code)
        # create zip of the directory
        zip_file = create_zip_file(trans_directory, language_code)
        # Send a Zip file of the content to the user
        return send_file(zip_file, as_attachment=True)
    else:
        return 'return_type may be missing: How do you want to get the data? zip or json'


def get_serialized_data(data):
    return [datum.serialize() for datum in data]


def send_response(message, error_code):
    error_message = json.dumps({'message': message})
    return abort(Response(error_message, error_code))


def manage_session(f):
    def inner(*args, **kwargs):
        # MANUAL PRE PING
        try:
            db.session.execute(text('SELECT 1;'))
            db.session.commit()
        except Exception:
            db.session.rollback()
        finally:
            db.session.close()

        # SESSION COMMIT, ROLLBACK, CLOSE
        try:
            res = f(*args, **kwargs)
            db.session.commit()
            return res
        except Exception as e:
            db.session.rollback()
            raise e
            # OR return traceback.format_exc()
        finally:
            db.session.close()
    return inner



def generate_csrf_token(url, app_key, app_secret, user_key, user_secret):
    '''
    Generate CSRF token for edit request

    Keyword arguments:
    app_key -- The application api auth key
    app_secret -- The application api auth secret
    user_key -- User auth key generated at login
    user_secret -- User secret generated at login
    '''
    # We authenticate the user using the keys
    auth = OAuth1(app_key, app_secret, user_key, user_secret)

    # Get token
    token_request = requests.get(url, params={
        'action': 'query',
        'meta': 'tokens',
        'format': 'json',
    }, auth=auth)
    token_request.raise_for_status()

    # We get the CSRF token from the result to be used in editing
    CSRF_TOKEN = token_request.json()['query']['tokens']['csrftoken']
    return CSRF_TOKEN, auth


def get_claim_options(wd_item_id, media_file_name):
    # generates a guid and attaches to wd_id
    return {
        'id': wd_item_id + '$' + str(uuid.uuid4()),
        'type': 'claim',
        'mainsnak': { 
            'snaktype': 'value',
            'property': 'P443',
            'datavalue': {
                'value': media_file_name,
                'type': 'commonsMedia'
            }
        }
    }


def get_language_qid(language):
    wb = Wikibase()
    items = wb.entity.search(language, 'de')
    for item in items['search']:
        if 'description' in item.keys():
            if 'language' in item['description']:
                return item['id']
    return None


def upload_file(file_data, username, lang_label, auth_obj, file_name):
    csrf_token, api_auth_token = generate_csrf_token(app.config['UPLOAD_API_URL'],
                                                auth_obj['consumer_key'],
                                                auth_obj['consumer_secret'],
                                                auth_obj['access_token'],
                                                auth_obj['access_secret'])
    params = {}
    params['action'] = 'upload'
    params['format'] = 'json'
    params['filename'] = file_name
    params['token'] = csrf_token
    params['text'] = "\n== {{int:license-header}} ==\n{{cc-by-sa-4.0}}\n\n[[Category:" +\
                     lang_label + " Pronunciation]]"

    response = requests.post(app.config['UPLOAD_API_URL'],
                            data=params,
                            auth=api_auth_token,
                            files={'file': io.BytesIO(file_data)})
    if response.status_code != 200:
        send_response('File was not uploaded', 401)
    return response


def make_edit_api_call(edit_type, username,language, lang_label,
                       data, wd_item, auth_object, file_name):

    csrf_token, api_auth_token = generate_csrf_token(app.config['API_URL'],
                                                 auth_object['consumer_key'],
                                                 auth_object['consumer_secret'],
                                                 auth_object['access_token'],
                                                 auth_object['access_secret'])
    edit_type = edit_type
    params = {}
    params['format'] = 'json'
    params['token'] = csrf_token
    params['summary'] = username + '@' + app.config['APP_NAME']

    if edit_type in ['wbsetlabel', 'wbsetdescription']:
        params['action'] = 'wbsetlabel' if edit_type == 'wbsetlabel' else 'wbsetdescription'
        params['language'] = language
        params['value'] = data
        params['id'] = wd_item

    else:
        params['action'] = 'wbcreateclaim'
        params['entity'] =  wd_item
        params['property'] = 'P443'
        params['snaktype'] =  'value'
        params['value'] = '"' + file_name + '"'

    revision_id = None

    if edit_type not in ['wbsetlabel', 'wbsetdescription']: # we upload a file
        upload_response = upload_file(data, username,lang_label, auth_object, file_name)

        if upload_response.status_code != 200:
            send_response('Upload failed', 401)

    claim_response = requests.post(app.config['API_URL'], data=params, auth=api_auth_token)

    if 'error' in claim_response.json().keys():
        return send_response(str(claim_response.json()['error']['code'].capitalize() +\
                                ': ' + claim_response.json()['error']['info'].capitalize()), 400)

    claim_result = claim_response.json()

    if edit_type in ['wbsetlabel', 'wbsetdescription'] and 'success' in claim_result.keys():
        entity  = claim_result.get('entity', None)
        revision_id = entity.get('lastrevid', None)
        return revision_id

    else:

        # get language item here from lang_code
        qualifier_value = get_language_qid(language)
        qualifier_params = {}
        qualifier_params['claim'] = claim_result['claim']['id']
        qualifier_params['action'] = 'wbsetqualifier'
        qualifier_params['property'] = 'P407'
        qualifier_params['snaktype'] = 'value'
        qualifier_params['value'] = json.dumps({'entity-type': 'item', 'id': qualifier_value})
        qualifier_params['format'] = 'json'
        qualifier_params['token'] = csrf_token
        qualifier_params['summary']  = username + '@' + app.config['APP_NAME']

        qual_response = requests.post(app.config['API_URL'],
                                        data=qualifier_params,
                                        auth=api_auth_token)

        qualifier_params = qual_response.json()

        if qual_response.status_code != 200:
            send_response('Qualifier could not be added', 401)
        if 'success' in qualifier_params.keys():
            revision_id = qualifier_params.get('pageinfo').get('lastrevid', None)
            return revision_id
        else:
            return send_response("Error: " + str(qual_response.json()['error']['info'].capitalize()), 400)
