import logging

from seafes.repo_data import repo_data
from seafes.indexes import RepoStatusIndex, RepoFilesIndex
from seafes.connection import es_get_conn
from seafes.config import seafes_config

logger = logging.getLogger('seafes')


def clear_deleted_repo_indices():
    repo_list = repo_data.get_all_repo_list()
    trash_repo_list = repo_data.get_all_trash_repo_list()
    repo_exist = [repo[0] for repo in repo_list]
    repo_exist.extend([repo[0] for repo in trash_repo_list])
    del repo_list
    del trash_repo_list

    try:
        status_index = RepoStatusIndex(es_get_conn(), seafes_config.repo_status_index_name)
        files_index = RepoFilesIndex(es_get_conn(), seafes_config.repo_files_index_name)
    except Exception as e:
        logger.error('Error:%s' % e)
        return
    repo_all = [r.get('id') for r in status_index.get_all_repos_from_index()]
    repo_deleted = set(repo_all) - set(repo_exist)
    logger.info("%d repos need to be deleted." % len(repo_deleted))
    for repo in repo_deleted:
        status_index.delete_repo(repo)
        files_index.delete_repo(repo)
        logger.info('repo %s has been removed' % repo)
    logger.info('Deleted repo removed success')


if __name__ == '__main__':
    clear_deleted_repo_indices()
