# coding: UTF-8
import logging
import posixpath

from seafes.commit_differ import CommitDiffer
from seafes.indexes import RepoStatusIndex, WikiIndex
from seafes.config import seafes_config
from seafes.indexes.wiki.wiki_index import WIKI_CONFIG_PATH, \
    WIKI_CONFIG_FILE_NAME, WIKI_DIRS

from seafobj import commit_mgr
from seafobj.exceptions import GetObjectError


logger = logging.getLogger('seafes')


MAX_ERRORS_ALLOWED = 1000


class WikiIndexUpdater(object):
    '''Update the wiki info index'''

    def __init__(self, es_conn):
        self.es_conn = es_conn

        self.status_index = RepoStatusIndex(es_conn, seafes_config.wiki_status_index_name)
        self.wiki_index = WikiIndex(es_conn, seafes_config.wiki_index_name)
        self.error_counter = 0

    def update_wiki_index(self, wiki_id, old_commit_id, new_commit_id):
        if old_commit_id == new_commit_id:
            return

        old_root = None
        if old_commit_id:
            try:
                old_commit = commit_mgr.load_commit(wiki_id, 0, old_commit_id)
                old_root = old_commit.root_id
            except GetObjectError as e:
                logger.debug(e)
                old_root = None

        try:
            new_commit = commit_mgr.load_commit(wiki_id, 0, new_commit_id)
        except GetObjectError as e:
            # new commit should exists in the obj store
            logger.warning(e)
            return

        new_root = new_commit.root_id
        version = new_commit.get_version()

        if old_root == new_root:
            return

        try:
            differ = CommitDiffer(wiki_id, version, old_root, new_root)
            added_files, deleted_files, added_dirs, deleted_dirs, modified_files = differ.diff(new_commit.ctime)
        except Exception as e:
            logger.warning('differ error: %s' % e)
            return

        # When the file is placed in the recycle bin, the index_json file is modified
        if not (added_files or deleted_dirs or modified_files):
            return
        old_cfg = self.wiki_index.get_wiki_conf(wiki_id, old_commit_id)
        new_cfg = self.wiki_index.get_wiki_conf(wiki_id, new_commit_id)
        prev_uuid_paths, prev_recycled_uuid_paths = self.wiki_index.get_uuid_path_mapping(old_cfg)
        curr_uuid_paths, curr_recycled_uuid_paths = self.wiki_index.get_uuid_path_mapping(new_cfg)

        recently_trashed_uuids = (
            prev_uuid_paths.keys() & curr_recycled_uuid_paths.keys()
        )
        self.wiki_index.delete_files(wiki_id, deleted_dirs, list(recently_trashed_uuids))

        need_added_files = added_files + modified_files

        # Check whether wiki title is changed
        # This is a necessary but not sufficient condition judgment.
        wiki_conf_path = posixpath.join(WIKI_CONFIG_PATH, WIKI_CONFIG_FILE_NAME)
        is_wiki_conf_modified = any(wiki_conf_path == tup[0].lstrip('/') for tup in need_added_files)

        if is_wiki_conf_modified:
            need_updated_title_uuids = self.wiki_index.get_updated_title_uuids(
                old_cfg, new_cfg, excluded_uuids=curr_recycled_uuid_paths.keys()
            )
        else:
            need_updated_title_uuids = set()

        recently_restore_uuid_to_path = {
            uuid: path
            for uuid, path in curr_uuid_paths.items()
            if uuid in prev_recycled_uuid_paths
        }

        get_title_name_path_by_conf = lambda conf: {
            page['docUuid']: (page.get('name'), page.get('path'))
            for page in conf.get('pages', [])
            if 'docUuid' in page
        }
        # {doc_uuid: (name, path)}
        title_info = get_title_name_path_by_conf(new_cfg)

        self.wiki_index.add_files(
            wiki_id,
            need_added_files,
            recently_restore_uuid_to_path,
            new_commit_id,
            need_updated_title_uuids,
            title_info
        )

    def check_recovery(self, wiki_id):
        status = self.status_index.get_repo_status(wiki_id)
        if status.need_recovery():
            logger.warning('%s: inrecovery', wiki_id)
            old = status.from_commit
            new = status.to_commit
            self.update_wiki_index(wiki_id, old, new)
            self.status_index.finish_update_repo(wiki_id, new)

    def update_wiki(self, wiki_id, latest_commit_id):
        self.check_recovery(wiki_id)

        status = self.status_index.get_repo_status(wiki_id)
        if latest_commit_id != status.from_commit:
            logger.info('Updating repo %s' % wiki_id)
            logger.debug('latest_commit_id: %s, status.from_commit: %s' %
                         (latest_commit_id, status.from_commit))
            old = status.from_commit
            new = latest_commit_id
            self.status_index.begin_update_repo(wiki_id, old, new)
            self.update_wiki_index(wiki_id, old, new)
            self.status_index.finish_update_repo(wiki_id, new)
        else:
            logger.debug('Wiki %s already uptodate', wiki_id)
