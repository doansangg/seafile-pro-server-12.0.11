# coding: UTF-8

from .indexes import RepoFilesIndex, WikiIndex
from .connection import es_get_conn
from seafes.config import seafes_config


def es_search(repos_map, search_path, keyword, obj_desc, start, size, search_filename_only=False):
    conn = es_get_conn()
    files_index = RepoFilesIndex(conn, seafes_config.repo_files_index_name)
    return files_index.search_files(repos_map, search_path, keyword, obj_desc, start, size, search_filename_only)


def es_wiki_search(wiki_id, keyword, count):
    conn = es_get_conn()
    wiki_index = WikiIndex(conn, seafes_config.wiki_index_name)
    return wiki_index.search_wikis(wiki_id, keyword, size=count)
