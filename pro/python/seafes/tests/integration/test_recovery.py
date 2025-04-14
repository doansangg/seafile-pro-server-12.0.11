from mock import patch
from seafes.indexes import FileIndexUpdater

from .utils import update_index_same_process, search_files
from seaserv import seafile_api

def test_recovery(repo):
    """
    When error happens during updating one repo, it can be recovered in the next
    time.
    """
    root = repo.get_dir('/')
    root.create_empty_file('foo.txt')
    update_index_same_process()
    repo_obj = seafile_api.get_repo(repo.id)
    assert '/foo.txt' in search_files({repo.id: repo_obj}, 'foo')

    root.create_empty_file('bar.txt')

    with patch.object(FileIndexUpdater, 'update_files_index') as mock_update:
        mock_update.side_effect = Exception('Mocked Exception for testing')
        update_index_same_process()

    assert '/bar.txt' not in search_files({repo.id: repo_obj}, 'bar')

    update_index_same_process()
    assert '/bar.txt' in search_files({repo.id: repo_obj}, 'bar')
