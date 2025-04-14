# coding: UTF-8

import logging

from ...commit_differ import CommitDiffer
from .. import RepoStatusIndex, RepoFilesIndex

from seafobj import commit_mgr
from seafobj.exceptions import GetObjectError
from seafes.config import seafes_config

logger = logging.getLogger('seafes')

MAX_ERRORS_ALLOWED = 1000

class FileIndexUpdater(object):
    '''Update the repo file info index'''

    def __init__(self, es_conn):
        self.es_conn = es_conn

        self.status_index = RepoStatusIndex(es_conn, seafes_config.repo_status_index_name)
        self.files_index = RepoFilesIndex(es_conn, seafes_config.repo_files_index_name)
        self.error_counter = 0

    def update_files_index(self, repo_id, old_commit_id, new_commit_id):
        if old_commit_id == new_commit_id:
            return

        old_root = None
        if old_commit_id:
            try:
                old_commit = commit_mgr.load_commit(repo_id, 0, old_commit_id)
                old_root = old_commit.root_id
            except GetObjectError as e:
                logger.debug(e)
                old_root = None

        try:
            new_commit = commit_mgr.load_commit(repo_id, 0, new_commit_id)
        except GetObjectError as e:
            # new commit should exists in the obj store
            logger.warning(e)
            return

        new_root = new_commit.root_id
        version = new_commit.get_version()

        try:
            self.files_index.update_repo_name_index(repo_id)
        except Exception as e:
            logger.warning('failed to update repo_name index, repo_id: %s, error: %s' % (repo_id, e))

        if old_root == new_root:
            return

        try:
            differ = CommitDiffer(repo_id, version, old_root, new_root)
            added_files, deleted_files, added_dirs, deleted_dirs, modified_files = differ.diff(new_commit.ctime)
        except Exception as e:
            logger.warning('differ error: %s' % e)
            return

        self.files_index.add_files(repo_id, version, added_files)
        self.files_index.delete_files(repo_id, deleted_files)
        self.files_index.add_dirs(repo_id, added_dirs)
        self.files_index.delete_dirs(repo_id, deleted_dirs)
        self.files_index.update_files(repo_id, version, modified_files)

    def check_recovery(self, repo_id):
        status = self.status_index.get_repo_status(repo_id)
        if status.need_recovery():
            logger.warning('%s: inrecovery', repo_id)
            old = status.from_commit
            new = status.to_commit
            self.update_files_index(repo_id, old, new)
            self.status_index.finish_update_repo(repo_id, new)

    def update_repo(self, repo_id, latest_commit_id):
        self.check_recovery(repo_id)

        status = self.status_index.get_repo_status(repo_id)
        if latest_commit_id != status.from_commit:
            logger.info('Updating repo %s' % repo_id)
            logger.debug('latest_commit_id: %s, status.from_commit: %s' %
                         (latest_commit_id, status.from_commit))
            old = status.from_commit
            new = latest_commit_id
            self.status_index.begin_update_repo(repo_id, old, new)
            self.update_files_index(repo_id, old, new)
            self.status_index.finish_update_repo(repo_id, new)
        else:
            logger.debug('Repo %s already uptodate', repo_id)
