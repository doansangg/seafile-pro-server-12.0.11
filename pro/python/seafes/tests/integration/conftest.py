# coding: UTF-8
try:
    from local_test_settings import *
except ImportError:
    pass

import os
from os.path import abspath, basename, dirname, join
import logging
import glob
from contextlib import contextmanager

from pytest import fixture, yield_fixture # pylint: disable=E0611
from mock import patch

os.environ['EVENTS_CONFIG_FILE'] = join(dirname(abspath(__file__)), 'seafevents.conf')

from seafes.config import seafes_config
from seafes.indexes import FileIndexUpdater

from .utils import (
    webapi, webapi_b, update_index, clear_index, search_files,
    randstring, get_test_resources
)

REPO_NAME_PREFIX = 'seafes-test-'

@contextmanager
def only_update_one_repo(repo_id):
    """
    Only update one repo during testing. This could speed up the tests
    significantly.
    """
    real_update_repo = FileIndexUpdater.update_repo

    def mock_update(self, r, *a):
        if r != repo_id:
            return
        real_update_repo(self, r, *a)

    with patch.object(FileIndexUpdater, 'update_repo', mock_update):
        yield

@yield_fixture(scope='function')
def repo():
    """Create a temporary repo, and remove it after testing"""
    name = REPO_NAME_PREFIX + randstring()
    desc = randstring()
    repo = webapi.repos.create_repo(name)
    print('[create repo] repo_id: %s' % repo.id)
    with only_update_one_repo(repo.id):
        try:
            yield repo
        finally:
            try:
                repo.delete()
            except:
                print("repo is deleted")

@yield_fixture(scope='function')
def another_repo():
    """Create a temporary repo, and remove it after testing"""
    name = REPO_NAME_PREFIX + randstring()
    desc = randstring()
    repo = webapi_b.repos.create_repo(name)
    print('[create another repo] repo_id: %s' % repo.id)
    with only_update_one_repo(repo.id):
        try:
            yield repo
        finally:
            try:
                repo.delete()
            except:
                print("another repo is deleted")

@yield_fixture(scope='function')
def use_chinese_lang():
    """Set lang = chinese in seafes config, for testing chinese-specific improvoments."""
    with patch.object(seafes_config, 'lang', 'chinese'):
        yield

@fixture(autouse=True)
def do_clear_index(caplog):
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('elasticsearch').setLevel(logging.INFO)
    caplog.set_level(logging.WARNING)
    clear_index()
    try:
        remove_test_repos()
    except:
        print("maybe some one be deleted")

def remove_test_repos():
    for repo in webapi.repos.list_repos():
        if repo.name.startswith(REPO_NAME_PREFIX):
            repo.delete()
