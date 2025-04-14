# coding: UTF-8

import os
import logging

from elasticsearch.exceptions import NotFoundError

from ..base import SeafileIndexBase

from ...extract import get_file_suffix, ExtractorFactory
from ...config import seafes_config

from ...repo_data import repo_data

logger = logging.getLogger('seafes')


class RepoFilesIndex(SeafileIndexBase):
    MAPPING = {
        '_source': {
            'enabled': True
        },
        'properties': {
            'repo': {
                'type': 'keyword',
            },
            'path': {
                'type': 'keyword',
            },
            'filename': {
                'type': 'text',
                'fields': {
                    'ngram': {
                        'type': 'text',
                        'index': True,
                        'analyzer': 'seafile_file_name_ngram_analyzer',
                    },
                },
            },
            'suffix': {
                'type': 'keyword',
            },
            'content': {
                'type': 'text',
                'term_vector': 'with_positions_offsets'
            },
            'is_dir': {
                'type': 'boolean',
            },
            'mtime': {
                'type': 'date',
            },
            'size': {
                'type': 'long'
            }
        },
    }

    index_settings = {
        'analysis': {
            'analyzer': {
                'seafile_file_name_ngram_analyzer': {
                    'type': 'custom',
                    'tokenizer': 'seafile_file_name_ngram_tokenizer',
                    'filter': [
                        'lowercase',
                    ],
                }
            },
            'tokenizer': {
                'seafile_file_name_ngram_tokenizer': {
                    'type': 'ngram',
                    'min_gram': '3',
                    'max_gram': '4',
                }
            }
        }
    }

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
        super(RepoFilesIndex, self).__init__(es)
        self.INDEX_NAME = index_name
        self.index_settings.update(self.shards_settings)
        self.language_index_optimization()
        self.create_index_if_missing(index_settings=self.index_settings)

    def language_index_optimization(self):
        if seafes_config.lang:
            # Use ngram for europe languages
            if seafes_config.lang != 'chinese':
                self.MAPPING['properties']['filename']['analyzer'] = seafes_config.lang
                self.MAPPING['properties']['content']['analyzer'] = seafes_config.lang
            else:
                # For chinese we don't need the ngram analyzer for file name.
                self.MAPPING['properties']['filename'].pop('fields', None)
                self.index_settings = self.shards_settings

                # Use the ik_smart analyzer to do coarse-grained chinese
                # tokenization for search keywords.
                self.MAPPING['properties']['filename']['analyzer'] = 'ik_smart'
                self.MAPPING['properties']['filename']['search_analyzer'] = 'ik_max_word'
                self.MAPPING['properties']['content']['analyzer'] = 'ik_smart'
                self.MAPPING['properties']['content']['search_analyzer'] = 'ik_smart'

    def is_chinese(self):
        return seafes_config.lang == 'chinese'

    def add_files(self, repo_id, version, files):
        # Index newly added files. For text files, also index their content.
        for path, obj_id, mtime, size in files:
            if len((repo_id + path).encode('utf-8')) <= 512:
                try:
                    self.add_file_to_index(repo_id, version, path, obj_id, mtime, size)
                except Exception as e:
                    logger.warning('failed to add file to index, repo_id: %s, path: %s, error: %s'
                                   % (repo_id, path, e))

    def add_dirs(self, repo_id, dirs):
        """Index newly added dirs.
        """
        for path, obj_id, mtime, size in dirs:
            if len((repo_id + path + '/').encode('utf-8')) <= 512:
                try:
                    self.add_dir_to_index(repo_id, path, mtime, size)
                except Exception as e:
                    logger.warning('failed to add file to index, repo_id: %s, path: %s, error: %s'
                                   % (repo_id, path, e))

    def add_file_to_index(self, repo_id, version, path, obj_id, mtime, size):
        """Add/update a file to/in index.
        """
        extractor = ExtractorFactory.get_extractor(os.path.basename(path))
        content = extractor.extract(repo_id, version, obj_id, path) if extractor else None
        filename = os.path.basename(path)

        try:
            eid = self.find_file_eid(repo_id, path)
        except Exception as e:
            logger.warning('failed to find_file_eid, %s(%s), %s(%s), error: %s',
                           repo_id, type(repo_id),
                           path, type(path), e)
            raise
        if eid:
            # This file already exists in index, we update it
            self.partial_update_file_content(eid, content, mtime, size)
        else:
            # This file does not exist in index
            suffix = get_file_suffix(filename)

            data = {
                'repo': repo_id,
                'path': path,
                'filename': filename,
                'suffix': suffix,
                'content': content,
                'is_dir': False,
                'mtime': mtime,
                'size': size,
                # 'tags': get_repo_file_tags(repo_id, path),
            }
            self.es.index(index=self.INDEX_NAME,
                          document=data,
                          id=repo_id + path)

    def update_repo_name_index(self, repo_id):
        if not repo_data.get_repo_name_mtime_size(repo_id):
            return
        repo = repo_data.get_repo_name_mtime_size(repo_id)[0]
        mtime = repo['update_time']
        size = repo['size']
        repo_name = repo['name']
        self.add_dir_to_index(repo_id, '/', mtime, size, repo_name)

    def add_dir_to_index(self, repo_id, path, mtime, size, repo_name=None):
        """Add a dir to index.
        """
        if path == '/':
            filename = repo_name
        else:
            filename = os.path.basename(path)

        path = path + '/' if path != '/' else path
        eid = repo_id + path

        data = {
            'repo': repo_id,
            'path': path,
            'filename': filename,
            'suffix': None,
            'content': None,
            'is_dir': True,
            'mtime': mtime,
            'size': size
        }
        self.es.index(
            index=self.INDEX_NAME,
            document=data,
            id=eid
        )

    def find_file_eid(self, repo_id, path):
        eid = repo_id + path
        try:
            self.es.get(index=self.INDEX_NAME, id=eid, _source_includes=[])
            return eid
        except NotFoundError:
            return None

    def partial_update_file_content(self, eid, content, mtime, size):
        doc = {
            'content': content,
            'mtime': mtime,
            'size': size
        }

        self.es.update(index=self.INDEX_NAME, id=eid, doc=doc)

    def delete_files(self, repo_id, files):
        actions = []
        for path in files:
            eid = repo_id + path
            actions.append({
                '_op_type': 'delete',
                '_index': self.INDEX_NAME,
                '_id': eid
            })
            self.bulk(actions, ignore_not_found=True)
        self.refresh()

    def delete_dirs(self, repo_id, dirs):
        for path in dirs:
            path = path + '/' if path != '/' else path
            self.delete_by_repo_path_prefix(repo_id, path)
        self.refresh()

    def delete_by_repo_path_prefix(self, repo_id, path_prefix):
        """Delete docs of dirs and all files/sub-dirs in those dirs of a repo.

        SQL: delete from repofiles where repo='xxx' and path like '/dir_xxx/%'
        """
        self.es.delete_by_query(index=self.INDEX_NAME, query={
            'bool': {
                'must': [
                    {'term': {'repo': repo_id}},
                    {'prefix': {'path': path_prefix}}
                ]
            }
        })

    def update_files(self, repo_id, version, files):
        self.add_files(repo_id, version, files)

    def delete_repo(self, repo_id):
        if len(repo_id) != 36:
            return

        self.delete_by_repo(repo_id)
        self.refresh()

    def delete_by_repo(self, repo_id):
        """Delete all the docs of a repo.

        SQL: delete from repofiles where repo='xxx'
        """
        self.es.delete_by_query(index=self.INDEX_NAME, query={
            'term': {
                'repo': repo_id
            }
        })

    def search_files(self, repos_map, search_path, keyword, obj_desc=None, start=0, size=10, search_filename_only=False):
        result = self.do_search(repos_map, search_path, keyword, obj_desc, start, size, search_filename_only)

        def get_entries(res):
            def _expand(value):
                return value[0] if isinstance(v, list) else v

            hits = res.get('hits', {}).get('hits', {})
            entries = []
            for e in hits:
                fields = e.get('_source', {})
                for k, v in fields.copy().items():
                    fields[k] = _expand(v)
                e['_source'] = fields
                entries.append(e)
            return entries

        total = result.get('hits', {}).get('total', {}).get('value', 0)
        ret = []

        for entry in get_entries(result):
            highlight = entry.get('highlight', {})

            content_highlight = '...'.join(highlight.get('content', []))
            d = entry['_source']
            r = {
                'repo_id': d['repo'],
                'fullpath': d['path'],
                'name': d['filename'],
                'is_dir': d['is_dir'],
                'score': entry['_score'],
                'content_highlight': content_highlight,
            }
            ret.append(r)

        return ret, total

    def _make_query_searches(self, keyword, search_filename_only=False):
        match_query_kwargs = {'minimum_should_match': '-25%'}

        def _make_match_query(field, key_word, **kw):
            q = {'query': key_word}
            q.update(kw)
            return {'match': {field: q}}

        def _make_match_phrase_query(field, key_word):
            return {'match_phrase': {field: {'query': key_word}}}

        searches = []

        if search_filename_only:
            searches.append(_make_match_query('filename', keyword, **match_query_kwargs))
            searches.append({
                'match': {
                    'filename.ngram': {
                        'query': keyword,
                        'minimum_should_match': '80%',
                    }
                }
            })
            return searches

        if self.is_chinese():
            match_query_kwargs['analyzer'] = 'ik_smart'
            phrase_list = keyword.split(' ')
            for phrase in phrase_list:
                if phrase.startswith('"') and phrase.endswith('"') or phrase.startswith('“') and phrase.endswith('”'):
                    searches.append(_make_match_phrase_query('filename', phrase))
                    searches.append(_make_match_phrase_query('content', phrase))
                else:
                    searches.append(_make_match_query('filename', phrase, **match_query_kwargs))
                    searches.append(_make_match_query('content', phrase, **match_query_kwargs))
        else:
            searches.append(_make_match_query('filename', keyword, **match_query_kwargs))
            searches.append(_make_match_query('content', keyword, **match_query_kwargs))
            searches.append({
                'match': {
                    'filename.ngram': {
                        'query': keyword,
                        'minimum_should_match': '80%',
                    }
                }
            })

        return searches

    def _add_repo_filter(self, query_map, repo_id):
        query_map['bool']['filter'].append({'term': {'repo': repo_id}})
        return query_map

    def _add_repos_filter(self, query_map, repos_map):
        origin_repo_ids = [repo.id for repo in list(repos_map.values()) if not repo.origin_repo_id]
        virtual_repos = [repo for repo in list(repos_map.values()) if repo.origin_repo_id]

        repo_search_dsl = []
        if origin_repo_ids:
            # append all origin repo to terms
            repo_search_dsl.append({'terms': {'repo': origin_repo_ids}})
        for repo in virtual_repos:
            # convert virtual_repo to origin_repo_id and origin_path
            repo_search_dsl.append({
                'bool': {
                    'must': [
                        {'term': {'repo': repo.origin_repo_id}},
                        {'prefix': {'path': repo.origin_path}}
                    ]
                }
            })

        if virtual_repos:
            # bool->should query
            query_map['bool']['filter'].append({
                'bool': {
                    'should': repo_search_dsl
                }
            })
        else:
            # simple query
            repo_filter = repo_search_dsl[0]
            query_map['bool']['filter'].append(repo_filter)

        return query_map

    def _add_suffix_filter(self, query_map, suffixes):
        if suffixes:
            if isinstance(suffixes, list):
                suffixes = [x.lower() for x in suffixes]
                query_map['bool']['filter'].append({'terms': {'suffix': suffixes}})
            else:
                query_map['bool']['filter'].append({'term': {'suffix': suffixes.lower()}})
        return query_map

    def _add_path_filter(self, query_map, search_path):
        if search_path is None:
            return query_map
        query_map['bool']['filter'].append({'prefix': {'path': search_path}})
        return query_map

    def _add_obj_type_filter(self, query_map, obj_type):
        if obj_type is None:
            return query_map
        elif obj_type == 'dir':
            query_map['bool']['filter'].append({'term': {'is_dir': True}})
        else:
            query_map['bool']['filter'].append({'term': {'is_dir': False}})
        return query_map

    def _get_search_range_dict(self, data_range):
        search_content = {}
        if data_range[0]:
            search_content['gte'] = data_range[0]
        if data_range[1]:
            search_content['lte'] = data_range[1]
        return search_content

    def is_valid_range(self, data_range):
        if not isinstance(data_range, tuple):
            return False
        if len(data_range) != 2:
            return False
        if all(e is None for e in data_range):
            return False
        return True

    def _add_time_range_filter(self, query_map, time_range):
        if not self.is_valid_range(time_range):
            return query_map
        search_content = self._get_search_range_dict(time_range)
        query_map['bool']['filter'].append({'range': {'mtime': search_content}})
        return query_map

    def _add_size_range_filter(self, query_map, size_range):
        if not self.is_valid_range(size_range):
            return query_map
        search_content = self._get_search_range_dict(size_range)
        query_map['bool']['filter'].append({'range': {'size': search_content}})
        return query_map

    def do_search(self, repos_map, search_path, keyword, obj_desc, start, size, search_filename_only=False):
        """Search files with providing ``keyword``.

        Arguments:
        - `self`:
        - `repos_map`: A directory of repo_id and repo_obj.
        - `keyword`: A search keyword provided by user.
        - `suffixes`: A list of file suffixes need to be searched.
        - `start`: How many initial results should be skipped.
        - `size`:  How many results should be returned.
        """
        if isinstance(obj_desc, dict):
            suffixes = obj_desc.get('suffixes', None)
            obj_type = obj_desc.get('obj_type', None)
            time_range = obj_desc.get('time_range', None)
            size_range = obj_desc.get('size_range', None)
        else:
            suffixes = None
            obj_type = None
            time_range = None
            size_range = None

        # clean invalid repo
        for key in list(repos_map.keys()):
            if not repos_map[key] or not hasattr(repos_map[key], 'origin_repo_id'):
                repos_map.pop(key)

        query_map = {'bool': {'filter': []}}
        # Constraints on the search environment
        if len(repos_map) == 1:
            repo_id = list(repos_map.keys())[0]
            repo = list(repos_map.values())[0]

            if hasattr(repo, 'origin_path') and repo.origin_path:
                search_path = os.path.join(repo.origin_path, search_path.strip('/'))\
                    if search_path else repo.origin_path

            query_map = self._add_repo_filter(query_map, repo_id)
            query_map = self._add_path_filter(query_map, search_path)
        elif len(repos_map) > 1:
            query_map = self._add_repos_filter(query_map, repos_map)

        if keyword:
            # Constraints on what you're searching for
            searches = self._make_query_searches(keyword, search_filename_only)
            query_map['bool']['should'] = searches
            query_map['bool']['minimum_should_match'] = 1

        query_map = self._add_suffix_filter(query_map, suffixes)
        query_map = self._add_obj_type_filter(query_map, obj_type)

        query_map = self._add_time_range_filter(query_map, time_range)
        query_map = self._add_size_range_filter(query_map, size_range)

        resp = self.es.search(
            index=self.INDEX_NAME, query=query_map, from_=start, size=size,
            source_includes=['repo', 'path', 'filename', 'is_dir'],
            highlight={
                'fields': {'content': {'type': seafes_config.highlight}},
                'pre_tags': ['<b>'],
                'post_tags': ['</b>'],
                'encoder': 'html',
                'require_field_match': True
            }
        )

        return resp
