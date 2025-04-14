# coding:utf-8
import time
import glob
import redis
import subprocess
from cgi import escape
from os.path import dirname, join

from .utils import search_files, get_test_resources, clear_index

master = None
worker = None
r = redis.Redis(host='localhost', port=6379)


def test_search_file_names(repo):
    prepare()
    try:    
        root = repo.get_dir('/')
        foo_txt = root.create_empty_file('foo.txt')
        time.sleep(5)
        assert '/foo.txt' in search_files(repo.id, 'foo')
        foo_txt.delete()
        time.sleep(5)
        assert '/foo.txt' not in search_files(repo.id, 'foo')
    finally:
        clear()

def test_search_file_chinese_file_name(repo):
    prepare()
    try:    
        root = repo.get_dir('/')
        foo_txt = root.create_empty_file('安平.txt')
        foo_txt = root.create_empty_file('平安科技.txt')

        time.sleep(5)
        assert '/安平.txt' in search_files(repo.id, '安平')
        assert '/平安科技.txt' in search_files(repo.id, '平安科')
        assert '/平安科技.txt' in search_files(repo.id, '平安')

        foo_txt.delete()
        time.sleep(5)
        assert '/安平.txt' in search_files(repo.id, '安平')
        assert '/平安科技.txt' not in search_files(repo.id, '平安')
    finally:
        clear()

def test_search_folder_names(repo):
    prepare()
    try:    
        root = repo.get_dir('/')
        foo_dir = root.mkdir('foo')
        root.mkdir('bar')
        time.sleep(5)

        assert '/foo/' in search_files(repo.id, 'foo')
        assert '/bar/' in search_files(repo.id, 'bar')

        foo_dir.create_empty_file('testfile.txt')
        time.sleep(5)
        assert '/foo/testfile.txt' in search_files(repo.id, 'testfile')

        foo_dir.delete()
        time.sleep(5)
        assert '/foo/testfile.txt' not in search_files(repo.id, 'testfile')
        assert '/foo/' not in search_files(repo.id, 'foo')
        assert '/bar/' in search_files(repo.id, 'bar')
    finally:
        clear()


def test_search_suffxies(repo):
    prepare()
    try:
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
        time.sleep(5)

        for suffix in suffixes:
            results = search_files(repo.id, 'foo', suffixes=[suffix])
            assert len(results) == 1
            path = '/foo.' + suffix
            assert path in results
    finally:
        clear()


def test_search_start_limit(repo):
    prepare()
    try:    
        root = repo.get_dir('/')
        N = 20
        for i in range(N):
            name = 'foo.{}'.format(i)
            root.create_empty_file(name)

        time.sleep(5)
        results = search_files(repo.id, 'foo', start=0, limit=10)
        assert len(results) == 10

        results = search_files(repo.id, 'foo', start=0, limit=20)
        assert len(results) == 20

        results = search_files(repo.id, 'foo', start=10, limit=20)
        assert len(results) == 10

        results = search_files(repo.id, 'foo', start=10, limit=1)
        assert len(results) == 1
    finally:
        clear()

def test_search_file_content(repo):
    prepare()
    try:    
        root = repo.get_dir('/')
        for path in glob.glob(join(dirname(__file__), 'data', '*')):
            if not path.endswith('.json'):
                root.upload_local_file(path)
        time.sleep(5)

        for keyword, matches in get_test_resources():
            results = search_files(repo.id, keyword)
            for match in matches:
                path = '/' + match
                assert path in results
    finally:
        clear()

def test_fulltext_index_size_limit(repo):
    prepare()
    try:    
        root = repo.get_dir('/')
        size_limit = 100 * 1024
        content = _make_content(size_limit / 2) + ' hello world'
        root.upload(content, 'foo.txt')
        content = _make_content(size_limit) + ' hello world'
        root.upload(content, 'foo2.txt')
        time.sleep(5)

        assert '/foo.txt' in search_files(repo.id, 'foo')
        assert '/foo2.txt' in search_files(repo.id, 'foo')
        assert '/foo2.txt' in search_files(repo.id, 'foo2')
        assert '/foo.txt' in search_files(repo.id, 'hello world')
        assert '/foo2.txt' not in search_files(repo.id, 'hello world')
    finally:
        clear()

def _make_content(size):
    return 'a ' * (size / 2)

def test_filename_ngram(repo):
    prepare()
    try:    
        root = repo.get_dir('/')
        root.create_empty_file('foobar.txt')

        time.sleep(5)
        assert '/foobar.txt' in search_files(repo.id, 'foo')
        assert '/foobar.txt' in search_files(repo.id, 'bar')
    finally:
        clear()

def test_filename_ik_smart(use_chinese_lang, repo): # pylint: disable=unused-argument
    prepare()
    try:    
        root = repo.get_dir('/')
        root.create_empty_file('公司交互规范.txt')
        root.create_empty_file('交互规范.txt')
        root.create_empty_file('规范.txt')
        root.create_empty_file('规.txt')
        root.create_empty_file('范.txt')

        time.sleep(5)
        hits = search_files(repo.id, '交互规范')
        assert '/公司交互规范.txt' in hits
        assert '/交互规范.txt' in hits
        assert '/规范.txt' not in hits
        assert '/规.txt' not in hits
        assert '/范.txt' not in hits

        hits = search_files(repo.id, '规范')
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

        time.sleep(5)
        hits = search_files(repo.id, '报表')
        assert '/九月报表.txt' in hits
        assert '/八月报表.txt' in hits
        assert '/报表.txt' in hits
        assert '/报.txt' not in hits
        assert '/表.txt' not in hits
        assert '/表格.txt' not in hits
    finally:
        clear()

def test_html_is_escape_properly(repo):
    prepare()
    try:    
        root = repo.get_dir('/')
        html_filename = 'markdown_with_html.txt'
        root.upload_local_file(join(dirname(__file__), 'data', html_filename))
        time.sleep(5)

        ret = search_files(repo.id, 'seafile')
        fullpath = '/{}'.format(html_filename)
        assert fullpath in ret

        entry = ret[fullpath]
        content_highlight = entry['content_highlight']

        assert '<p><div class="toc">' not in content_highlight
        assert escape('<p><div class="toc">', quote=True) in content_highlight
    finally:
        clear()


def start_master():
    global master
    master_args = 'python -m seafes.index_master start'
    master = subprocess.Popen(master_args.split())

def start_worker():
    global worker
    worker_args = 'python -m seafes.index_worker start'
    worker = subprocess.Popen(worker_args.split())


def stop_master():
    master.kill()

def stop_worker():
    worker.kill()

def clear_index_task():
    r.delete('index_task')

def prepare():
    clear_index_task()
    clear_index()
    start_master()
    time.sleep(1)
    start_worker()

def clear():
    stop_worker()
    time.sleep(2)
    stop_master()
