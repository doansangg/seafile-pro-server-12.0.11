# coding: UTF-8

import json
import posixpath
import logging

from seafes.indexes.base import SeafileIndexBase
from seafes.constants import ZERO_OBJ_ID
from seafes.extract import extract_sdoc_text
from seafes.config import seafes_config
from seafobj import fs_mgr
from seaserv import seafile_api


logger = logging.getLogger('seafes')


WIKI_CONFIG_PATH = '_Internal/Wiki'
WIKI_CONFIG_FILE_NAME = 'index.json'
WIKI_DIRS = ['wiki-pages']


class WikiIndex(SeafileIndexBase):
    INDEX_WIKI_SIZE_LIMIT = seafes_config.office_file_size_limit
    MAPPING = {
        '_source': {
            'enabled': True
        },
        'properties': {
            'wiki_id': {
                'type': 'keyword',
            },
            'doc_uuid':{
                'type': 'keyword',
            },
            'content': {
                'type': 'text',
                'term_vector': 'with_positions_offsets'
            },
            'title': {
                'type': 'text',
                'term_vector': 'with_positions_offsets'
            },
        },
    }

    index_settings = {}

    shards_settings = {
        'index': {
            'number_of_shards': seafes_config.shards,
        }
    }

    def __init__(self, es, index_name):
        """
        Init function.

        :type es: elasticsearch.Elasticsearch
        """
        super(WikiIndex, self).__init__(es)
        self.INDEX_NAME = index_name
        self.index_settings.update(self.shards_settings)
        self.language_index_optimization()
        self.create_index_if_missing(index_settings=self.index_settings)

    def language_index_optimization(self):
        if seafes_config.lang:
            # Use ngram for europe languages
            if seafes_config.lang != 'chinese':
                self.MAPPING['properties']['content']['analyzer'] = seafes_config.lang
                self.MAPPING['properties']['title']['analyzer'] = seafes_config.lang
            else:
                self.index_settings = self.shards_settings

                # Use the ik_smart analyzer to do coarse-grained chinese
                # tokenization for search keywords.
                self.MAPPING['properties']['content']['analyzer'] = 'ik_smart'
                self.MAPPING['properties']['content']['search_analyzer'] = 'ik_smart'
                self.MAPPING['properties']['title']['analyzer'] = 'ik_smart'
                self.MAPPING['properties']['title']['search_analyzer'] = 'ik_smart'

    def is_chinese(self):
        return seafes_config.lang == 'chinese'

    def get_wiki_content(self, wiki_id, obj_id):
        if obj_id == ZERO_OBJ_ID:
            return None
        f = fs_mgr.load_seafile(wiki_id, 1, obj_id)
        b_content = f.get_content()
        if not b_content.strip():
            return None
        content = extract_sdoc_text(b_content).strip()
        if isinstance(content, bytes):
            return content.decode('utf-8')

        return content

    def get_wiki_conf(self, wiki_id, commit_id=None):
        # Get wiki config dict
        conf_path = posixpath.join(WIKI_CONFIG_PATH, WIKI_CONFIG_FILE_NAME)
        if commit_id == ZERO_OBJ_ID:
            return None

        if commit_id is not None:
            file_id = seafile_api.get_file_id_by_commit_and_path(wiki_id, commit_id, conf_path)
        else:
            file_id = seafile_api.get_file_id_by_path(wiki_id, conf_path)
        if file_id is None:
            return None
        f = fs_mgr.load_seafile(wiki_id, 1, file_id)
        return json.loads(f.get_content().decode())

    def get_updated_title_uuids(self, old_conf, new_conf, excluded_uuids):
        """Calculate the items that are in new_conf but not in old_conf,
        or the names in New_conf are different from the names in old_conf.
        return based on new_conf data
        Args:
            old_conf: get from get_wiki_conf
            new_conf: get from get_wiki_conf
            excluded_uuids: set of doc_uuids that should be excluded from the result
        Returns:
            set: A set of doc_uuids for updated titles."""

        old_pages = {page['id']: page for page in old_conf['pages']} if old_conf else {}
        new_pages = {page['id']: page for page in new_conf['pages']} if new_conf else {}

        doc_uuids = set()
        for new_id, new_page in new_pages.items():
            if new_id not in old_pages or new_page['name'] != old_pages[new_id]['name']:
                if new_page['docUuid'] not in excluded_uuids:
                    doc_uuids.add(new_page['docUuid'])

        return doc_uuids

    def get_uuid_path_mapping(self, config):
        """Determine the UUID-PATH mapping for extracting unremoved or deleted wiki pages
        """
        def extract_ids_from_navigation(navigation_items, navigation_ids):
            for item in navigation_items:
                navigation_ids.add(item['id'])
                if 'children' in item and item['children']:
                    extract_ids_from_navigation(item['children'], navigation_ids)
        if config is None:
            return {}, {}
        navigation_ids = set()
        extract_ids_from_navigation(config['navigation'], navigation_ids)

        uuid_to_path, rm_uuid_to_path = {}, {}
        for page in config['pages']:
            if page['id'] in navigation_ids:
                uuid_to_path[page['docUuid']] = page['path']
            else:
                rm_uuid_to_path[page['docUuid']] = page['path']

        return uuid_to_path, rm_uuid_to_path

    def add_files(self, wiki_id, files, uuid_path, commit_id, updated_title_uuids, title_info):
        """Add wiki files to the index
        Args:
            wiki_id: str
            files: list
            uuid_path: dict
            commit_id: str
            updated_title_uuids: set
            title_info: dict: {doc_uuid: (name, path)}
            """

        for path, obj_id, mtime, size in files:
            if not self.is_wiki_page(path):
                continue
            if int(size) >= int(self.INDEX_WIKI_SIZE_LIMIT):
                continue
            doc_uuid = path.split('/')[2]
            if not title_info.get(doc_uuid):
                continue
            # remove docuuid from updated_title_uuids if it is in the need updated files
            # this is for the case: both the title and content are updated
            updated_title_uuids.discard(doc_uuid)
            content = self.get_wiki_content(wiki_id, obj_id)
            title = title_info.get(doc_uuid)[0]
            data = {
                'wiki_id': wiki_id,
                'doc_uuid': doc_uuid,
                'content': content,
                'title': title
            }
            self.es.index(index=self.INDEX_NAME,
                        document=data,
                        id= wiki_id + '_' + doc_uuid)

        # Recovered files
        for doc_uuid, path in uuid_path.items():
            updated_title_uuids.discard(doc_uuid)
            file_id = seafile_api.get_file_id_by_commit_and_path(wiki_id, commit_id, path)
            content = self.get_wiki_content(wiki_id, file_id)
            title = title_info.get(doc_uuid)[0]
            data = {
                'wiki_id': wiki_id,
                'doc_uuid': doc_uuid,
                'content': content,
                'title': title
            }
            self.es.index(index=self.INDEX_NAME,
                        document=data,
                        id= wiki_id + '_' + doc_uuid)


        # For the case: only title is updated
        for doc_uuid in updated_title_uuids:
            f_path = title_info.get(doc_uuid)[1]
            file_id = seafile_api.get_file_id_by_commit_and_path(wiki_id, commit_id, f_path)
            content = self.get_wiki_content(wiki_id, file_id)
            title = title_info.get(doc_uuid)[0]
            data = {
                'wiki_id': wiki_id,
                'doc_uuid': doc_uuid,
                'content': content,
                'title': title
            }
            self.es.index(index=self.INDEX_NAME,
                        document=data,
                        id= wiki_id + '_' + doc_uuid)

    def delete_files(self, wiki_id, dirs, doc_uuids):
        actions = []
        for path in dirs:
            if not self.is_wiki_page(path):
                continue
            doc_uuid = path.split('/')[2]
            eid = wiki_id + '_' + doc_uuid
            actions.append({
                '_op_type': 'delete',
                '_index': self.INDEX_NAME,
                '_id': eid
            })
            self.bulk(actions, ignore_not_found=True)
        actions.clear()
        for doc_uuid in doc_uuids:
            eid = wiki_id + '_' + doc_uuid
            actions.append({
                '_op_type': 'delete',
                '_index': self.INDEX_NAME,
                '_id': eid
            })
            self.bulk(actions, ignore_not_found=True)
        self.refresh()

    def delete_wiki(self, wiki_id):
        if len(wiki_id) != 36:
            return

        self.delete_by_wiki_id(wiki_id)
        self.refresh()

    def delete_by_wiki_id(self, wiki_id):
        self.es.delete_by_query(index=self.INDEX_NAME, query={
            'term': {
                'wiki_id': wiki_id
            }
        })

    def search_wikis(self, wiki_id, keyword, start=0, size=10):
        result = self.do_search(wiki_id, keyword, start, size)
        ret = []
        hits = result.get('hits', {}).get('hits', [])
        for hit in hits:
            r = {
                '_id': hit.get('_id'),
                'score': hit.get('_score'),
                'wiki_id': hit.get('_source', {}).get('wiki_id'),
                'doc_uuid': hit.get('_source', {}).get('doc_uuid'),
            }
            if highlight_content := hit.get('highlight', {}).get('content', [None])[0]:
                r.update(content=highlight_content)
            if highlight_title := hit.get('highlight', {}).get('title', [None])[0]:
                r.update(title=highlight_title)
            ret.append(r)

        return ret

    def _make_query_searches(self, keyword):
        match_query_kwargs = {'minimum_should_match': '-25%'}

        def _make_match_query(field, key_word, **kw):
            q = {'query': key_word}
            q.update(kw)
            return {'match': {field: q}}

        def _make_match_phrase_query(field, key_word):
            return {'match_phrase': {field: {'query': key_word}}}

        searches = []

        if self.is_chinese():
            match_query_kwargs['analyzer'] = 'ik_smart'
            phrase_list = keyword.split(' ')
            for phrase in phrase_list:
                if phrase.startswith('"') and phrase.endswith('"') or phrase.startswith('“') and phrase.endswith('”'):
                    searches.append(_make_match_phrase_query('content', phrase))
                    searches.append(_make_match_phrase_query('title', phrase))
                else:
                    searches.append(_make_match_query('content', phrase, **match_query_kwargs))
                    searches.append(_make_match_query('title', phrase, **match_query_kwargs))
        else:
            searches.append(_make_match_query('content', keyword, **match_query_kwargs))
            searches.append(_make_match_query('title', keyword, **match_query_kwargs))

        return searches

    def _add_wiki_filter(self, query_map, wiki_id):
        query_map['bool']['filter'].append({'term': {'wiki_id': wiki_id}})
        return query_map

    def do_search(self, wiki_id, keyword, start, size):
        query_map = {'bool': {'filter': [], 'should': [], 'minimum_should_match': 1}}
        query_map = self._add_wiki_filter(query_map, wiki_id)

        # Constraints on what you're searching for
        searches = self._make_query_searches(keyword)
        query_map['bool']['should'] = searches
        resp = self.es.search(
            index=self.INDEX_NAME,
            query=query_map,
            from_=start,
            size=size,
            source_includes=['wiki_id', 'doc_uuid', 'content', 'title'],
            highlight={
                'fields': {
                    'content': {'type': seafes_config.highlight},
                    'title': {'type': seafes_config.highlight},
                },
                'pre_tags': ['<mark>'],
                'post_tags': ['</mark>'],
                'encoder': 'html',
                'require_field_match': True,
            },
        )

        return resp

    @staticmethod
    def is_wiki_page(path):
        if path.split('/')[1] in WIKI_DIRS and path.endswith('.sdoc'):
            return True
        return False
