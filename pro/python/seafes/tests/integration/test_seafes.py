# coding: UTF-8

from cgi import escape
import time
import glob
from os.path import dirname, join
from .utils import (
    update_index, search_files,
    get_test_resources, ANOTHER_USER
)

from seaserv import seafile_api

def test_search_file_names(repo):
    root = repo.get_dir('/')
    foo_txt = root.create_empty_file('foo.txt')
    repo_obj = seafile_api.get_repo(repo.id)

    update_index()
    assert '/foo.txt' in search_files({repo.id: repo_obj}, 'foo')

    foo_txt.delete()
    update_index()
    assert '/foo.txt' not in search_files({repo.id: repo_obj}, 'foo')

def test_search_file_with_diff_path(repo):
    root = repo.get_dir('/')
    game_folder = root.mkdir('game')
    test_folder = root.mkdir('test')
    game_folder.create_empty_file('foo')
    test_folder.create_empty_file('foo')
    root.create_empty_file('foo')
    update_index()

    repo_obj = seafile_api.get_repo(repo.id)
    assert len(search_files({repo.id: repo_obj}, 'foo', search_path=root.path)) == 3
    assert len(search_files({repo.id: repo_obj}, 'foo', search_path=game_folder.path)) == 1
    assert len(search_files({repo.id: repo_obj}, 'foo', search_path=test_folder.path)) == 1

def test_search_file_chinese_file_name(repo):
    root = repo.get_dir('/')
    foo_txt = root.create_empty_file('安平.txt')
    foo_txt = root.create_empty_file('平安科技.txt')
    repo_obj = seafile_api.get_repo(repo.id)

    update_index()
    assert '/安平.txt' in search_files({repo.id: repo_obj}, '安平')
    assert '/平安科技.txt' in search_files({repo.id: repo_obj}, '平安')
    assert '/平安科技.txt' in search_files({repo.id: repo_obj}, '平安科')

    foo_txt.delete()
    update_index()
    assert '/安平.txt' in search_files({repo.id: repo_obj}, '安平')
    assert '/平安科技.txt' not in search_files({repo.id: repo_obj}, '平安')

def test_search_folder_names(repo):
    root = repo.get_dir('/')
    foo_dir = root.mkdir('foo')
    root.mkdir('bar')
    update_index()

    repo_obj = seafile_api.get_repo(repo.id)
    assert '/foo/' in search_files({repo.id: repo_obj}, 'foo')
    assert '/bar/' in search_files({repo.id: repo_obj}, 'bar')

    foo_dir.create_empty_file('testfile.txt')
    update_index()
    assert '/foo/testfile.txt' in search_files({repo.id: repo_obj}, 'testfile')

    foo_dir.delete()
    update_index()
    assert '/foo/testfile.txt' not in search_files({repo.id: repo_obj}, 'testfile')
    assert '/foo/' not in search_files({repo.id: repo_obj}, 'foo')
    assert '/bar/' in search_files({repo.id: repo_obj}, 'bar')

def test_search_suffxies(repo):
    root = repo.get_dir('/')
    suffixes = (
        'txt',
        'pdf',
        'docx',
        'pptx',
        'xlsx',
        'c',
        'cpp',
        'h',
    )
    for suffix in suffixes:
        root.create_empty_file('foo.' + suffix)
    update_index()

    repo_obj = seafile_api.get_repo(repo.id)
    for suffix in suffixes:
        obj_desc = {
            'suffixes': [suffix]
        }
        results = search_files({repo.id: repo_obj}, 'foo', obj_desc=obj_desc)
        assert len(results) == 1
        path = '/foo.' + suffix
        assert path in results

def test_search_start_limit(repo):
    root = repo.get_dir('/')
    N = 20
    for i in range(N):
        name = 'foo.{}'.format(i)
        root.create_empty_file(name)

    update_index()
    repo_obj = seafile_api.get_repo(repo.id)
    results = search_files({repo.id: repo_obj}, 'foo', start=0, limit=10)
    assert len(results) == 10

    results = search_files({repo.id: repo_obj}, 'foo', start=0, limit=20)
    assert len(results) == 20

    results = search_files({repo.id: repo_obj}, 'foo', start=10, limit=20)
    assert len(results) == 10

    results = search_files({repo.id: repo_obj}, 'foo', start=10, limit=1)
    assert len(results) == 1

def test_search_with_obj_type(repo):
    root = repo.get_dir('/')
    root.create_empty_file('foobar.txt')
    root.mkdir('foobar')
    root.create_empty_file('foobar1.txt')
    update_index()
    repo_obj = seafile_api.get_repo(repo.id)
    results = search_files({repo.id: repo_obj}, 'foobar')
    assert len(results) == 3
    obj_desc = {'obj_type': 'dir'}
    results = search_files({repo.id: repo_obj}, 'foobar', obj_desc=obj_desc)
    assert len(results) == 1
    obj_desc = {'obj_type': 'file'}
    results = search_files({repo.id: repo_obj}, 'foobar', obj_desc=obj_desc)
    assert len(results) == 2


def test_search_file_content(repo):
    root = repo.get_dir('/')
    for path in glob.glob(join(dirname(__file__), 'data', '*')):
        if not path.endswith('.json'):
            root.upload_local_file(path)
    update_index()

    repo_obj = seafile_api.get_repo(repo.id)
    for keyword, matches in get_test_resources():
        results = search_files({repo.id: repo_obj}, keyword)
        for match in matches:
            path = '/' + match
            assert path in results

def test_fulltext_index_size_limit(repo):
    root = repo.get_dir('/')
    size_limit = 100 * 1024
    content = _make_content(size_limit / 2) + ' hello world'
    root.upload(content, 'foo.txt')
    content = _make_content(size_limit) + ' hello world'
    root.upload(content, 'foo2.txt')
    update_index()

    repo_obj = seafile_api.get_repo(repo.id)
    assert '/foo.txt' in search_files({repo.id: repo_obj}, 'foo')
    assert '/foo2.txt' in search_files({repo.id: repo_obj}, 'foo2')
    assert '/foo.txt' in search_files({repo.id: repo_obj}, 'hello world')
    assert '/foo2.txt' not in search_files({repo.id: repo_obj}, 'hello world')

def _make_content(size):
    return 'a ' * (size / 2)

def test_filename_ngram(repo):
    root = repo.get_dir('/')
    root.create_empty_file('foobar.txt')

    update_index()
    repo_obj = seafile_api.get_repo(repo.id)
    assert '/foobar.txt' in search_files({repo.id: repo_obj}, 'foo')
    assert '/foobar.txt' in search_files({repo.id: repo_obj}, 'bar')

def test_filename_ik_smart(use_chinese_lang, repo): # pylint: disable=unused-argument
    root = repo.get_dir('/')
    root.create_empty_file('公司交互规范.txt')
    root.create_empty_file('交互规范.txt')
    root.create_empty_file('规范.txt')
    root.create_empty_file('规.txt')
    root.create_empty_file('范.txt')

    update_index()
    repo_obj = seafile_api.get_repo(repo.id)
    hits = search_files({repo.id: repo_obj}, '交互规范')
    assert '/公司交互规范.txt' in hits
    assert '/交互规范.txt' in hits
    assert '/规范.txt' not in hits
    assert '/规.txt' not in hits
    assert '/范.txt' not in hits

    hits = search_files({repo.id: repo_obj}, '规范')
    assert '/公司交互规范.txt' in hits
    assert '/交互规范.txt' in hits
    assert '/规范.txt' in hits
    assert '/规.txt' not in hits
    assert '/范.txt' not in hits

    root.create_empty_file('九月报表.txt')
    root.create_empty_file('八月报表.txt')
    root.create_empty_file('报表.txt')
    root.create_empty_file('报.txt')
    root.create_empty_file('表.txt')
    root.create_empty_file('表格.txt')

    update_index()
    hits = search_files({repo.id: repo_obj}, '报表')
    assert '/九月报表.txt' in hits
    assert '/八月报表.txt' in hits
    assert '/报表.txt' in hits
    assert '/报.txt' not in hits
    assert '/表.txt' not in hits
    assert '/表格.txt' not in hits

def test_html_is_escape_properly(repo):
    root = repo.get_dir('/')
    html_filename = 'markdown_with_html.txt'
    root.upload_local_file(join(dirname(__file__), 'data', html_filename))
    update_index()

    repo_obj = seafile_api.get_repo(repo.id)
    ret = search_files({repo.id: repo_obj}, 'seafile')
    fullpath = '/{}'.format(html_filename)
    assert fullpath in ret

    entry = ret[fullpath]
    content_highlight = entry['content_highlight']

    assert '<p><div class="toc">' not in content_highlight
    assert escape('<p><div class="toc">', quote=True) in content_highlight

def test_search_shared_subdir(repo, another_repo):
    root = repo.get_dir('/')
    another_root = another_repo.get_dir('/')

    repo_obj = seafile_api.get_repo(repo.id)
    subdir = root.mkdir('test')
    subdir.create_empty_file('foo.txt')
    assert subdir.share_to_user(ANOTHER_USER, 'rw')
    virtual_repo = seafile_api.get_virtual_repo(repo.id, subdir.path, repo.client.username)

    update_index()
    assert '/test/foo.txt' in search_files({repo.id: virtual_repo}, 'foo')

def test_search_shared_subdir_with_prefix(repo, another_repo):
    root = repo.get_dir('/')
    another_root = another_repo.get_dir('/')

    repo_obj = seafile_api.get_repo(repo.id)
    subdir = root.mkdir('test')
    ssdir = subdir.mkdir('folder')
    ssdir.create_empty_file('foo.txt')
    assert subdir.share_to_user(ANOTHER_USER, 'rw')
    virtual_repo = seafile_api.get_virtual_repo(repo.id, subdir.path, repo.client.username)

    update_index()
    assert '/test/folder/foo.txt' in search_files({repo.id: virtual_repo}, 'foo', search_path='/folder')

def test_search_multi_repo(repo, another_repo):
    root = repo.get_dir('/')
    another_root = another_repo.get_dir('/')

    repo_obj = seafile_api.get_repo(repo.id)
    another_repo_obj = seafile_api.get_repo(another_repo.id)
    root.create_empty_file('foo.txt')
    another_root.create_empty_file('handsome.md')

    update_index()
    assert '/foo.txt' in search_files({repo.id: repo_obj, another_repo.id: another_repo_obj}, 'foo')
    assert '/handsome.md' in search_files({repo.id: repo_obj, another_repo.id: another_repo_obj}, 'handsome')

    assert '/foo.txt' in search_files({repo.id: repo_obj, another_repo.id: another_repo_obj}, 'foo', search_path='/test')
    assert '/handsome.md' in search_files({repo.id: repo_obj, another_repo.id: another_repo_obj}, 'handsome', search_path='/test')

def test_search_outside_file(repo, another_repo):
    root = repo.get_dir('/')
    another_root = another_repo.get_dir('/')
    root.create_empty_file('outside.md')
    another_root.create_empty_file('inside.py')
    subdir = root.mkdir('subdir')
    assert subdir.share_to_user(ANOTHER_USER, 'rw')
    virtual_repo = seafile_api.get_virtual_repo(repo.id, subdir.path, repo.client.username)

    another_repo_obj = seafile_api.get_repo(another_repo.id)
    origin_repo_obj = seafile_api.get_repo(repo.id)

    update_index()
    assert '/outside.md' in search_files({repo.id: origin_repo_obj, another_repo.id: another_repo_obj}, 'outside')
    assert '/outside.md' not in search_files({repo.id: virtual_repo, another_repo.id: another_repo_obj}, 'outside')

def test_search_by_time(repo):
    root = repo.get_dir('/')
    root.create_empty_file('outside.md')
    time.sleep(1)
    d = int(time.time())
    time.sleep(1)
    root.create_empty_file('outside1.md')
    root.create_empty_file('outside2.md')

    update_index()
    repo_obj = seafile_api.get_repo(repo.id)

    assert len(search_files({repo.id: repo_obj}, 'outside')) == 3

    obj_desc = {
        'time_range': (d, None)
    }
    assert '/outside1.md' in search_files({repo.id: repo_obj}, 'outside', obj_desc=obj_desc)
    assert '/outside2.md' in search_files({repo.id: repo_obj}, 'outside', obj_desc=obj_desc)
    assert len(search_files({repo.id: repo_obj}, 'outside', obj_desc=obj_desc)) == 2

    obj_desc = {
        'time_range': (None, d)
    }
    assert '/outside.md' in search_files({repo.id: repo_obj}, 'outside', obj_desc=obj_desc)
    assert len(search_files({repo.id: repo_obj}, 'outside', obj_desc=obj_desc)) == 1

def test_search_by_size(repo):
    root = repo.get_dir('/')
    xls_filename = 'simple_spreadsheet.xls'
    root.upload_local_file(join(dirname(__file__), 'data', xls_filename))
    txt_filename = 'simple_text.txt'
    root.upload_local_file(join(dirname(__file__), 'data', txt_filename))

    update_index()
    repo_obj = seafile_api.get_repo(repo.id)

    assert len(search_files({repo.id: repo_obj}, 'simple')) == 2

    obj_desc = {
        'size_range': (100, None)
    }
    assert len(search_files({repo.id: repo_obj}, 'simple', obj_desc=obj_desc)) == 1
    assert '/' + xls_filename in search_files({repo.id: repo_obj}, 'simple', obj_desc=obj_desc)

    obj_desc = {
        'size_range': (None, 100)
    }
    assert len(search_files({repo.id: repo_obj}, 'simple', obj_desc=obj_desc)) == 1
    assert '/' + txt_filename in search_files({repo.id: repo_obj}, 'simple', obj_desc=obj_desc)
