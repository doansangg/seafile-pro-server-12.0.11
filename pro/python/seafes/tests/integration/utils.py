import os
import json
import time
import random
import string # pylint: disable=W0402
from os.path import dirname, join
from subprocess import check_call

import seafileapi

import seafes
from seafes.indexes.repo_file import index_local
from seafes.indexes.repo_file.index_local import start_index_local, check_concurrent_update

USER = os.environ.get('SEAFILE_TEST_USERNAME', 'test@seafiletest.com')
PASSWORD = os.environ.get('SEAFILE_TEST_PASSWORD', 'testtest')
# Use seafile web api to manipulate repos/files
webapi = seafileapi.connect('http://127.0.0.1:8000', USER, PASSWORD)

ANOTHER_USER = os.environ.get('SEAFILE_TEST_USERNAME', 'test@seafestest.com')
ANOTHER_PASSWORD = os.environ.get('SEAFILE_TEST_PASSWORD', 'testtest')
webapi_b = seafileapi.connect('http://127.0.0.1:8000', ANOTHER_USER, ANOTHER_PASSWORD)
DEVNULL = open(os.devnull, 'wb')

def randstring(length=20):
    return ''.join(random.choice(string.ascii_lowercase) for i in range(length))

def _run_seafes_cmd(cmd):
    args = [
        'python',
        '-m', 'seafes.indexes.repo_file.index_local',
        '--loglevel', 'debug',
        cmd
    ]
    # check_output(args)
    check_call(args, stdout=DEVNULL, stderr=DEVNULL)

def clear_index():
    _run_seafes_cmd('clear')

def update_index():
    _run_seafes_cmd('update')

def search_files(repos_map, pattern, search_path=None, obj_desc=None, start=0, limit=10):
    if obj_desc is None:
        obj_desc = {}
    results = {}
    entries, _ = seafes.es_search(repos_map, search_path, pattern, obj_desc, start, limit)
    for entry in entries:
        results[entry['fullpath']] = entry
    return results

def get_test_resources():
    path = join(dirname(__file__), 'data', 'file_content.json')
    with open(path, 'r') as fp:
        for line in fp:
            obj = json.loads(line.strip())
            yield obj['keyword'], obj['matches']

def update_index_same_process():
    """ function used for update indices in same process.
    it will clear indices and then start to index indices, then wait task finish and remove lock file.
    """
    index_local.NO_TASKS = False
    clear_index()
    start_index_local()
    while not check_concurrent_update():
        time.sleep(1)
    os.remove('update.lock')

# update_index = update_index_same_process
