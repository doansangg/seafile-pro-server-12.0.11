from .utils import update_index, search_files
from seaserv import seafile_api


def test_default(repo):
    root = repo.get_dir('/')
    root.create_empty_file('foo.txt')
    update_index()
    repo_obj = seafile_api.get_repo(repo.id)

    assert '/foo.txt' in search_files({repo.id: repo_obj}, 'foo')

    repo.delete()
    update_index()
    assert '/foo.txt' not in search_files({repo.id: repo_obj}, 'foo')

def test_invalid_repo_maps(repo):
    root = repo.get_dir('/')
    root.create_empty_file('foo.txt')
    update_index()
    repo_obj = seafile_api.get_repo(repo.id)

    assert '/foo.txt' in search_files({repo.id: None}, 'foo')

    repo.delete()
    update_index()
    assert '/foo.txt' not in search_files({repo.id: None}, 'foo')
