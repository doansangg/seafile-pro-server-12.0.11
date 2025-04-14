# Seafile 搜索配置

## 安装

### elasticsearch-py

    pip install elasticsearch==8.5.2

### seafobj

    git clone git://github.com/haiwen/seafobj.git

### elasticsearch

    git clone git://github.com/seafileltd/elasticsearch-bin.git
    cd elasticsearch-bin
    tar xf elasticsearch.tar.gz

### 其他

* 生成 ExtractText.jar ， 用于 office 文件的文本提取

    cd seafes
    make

* 安装 pdftotext, 用于 pdf 文件提取

    sudo apt-get install poppler-utils

如果是 mac, 则 `sudo port install poppler`


## 配置

  把 seafes 目录下的 run.sh.template 复制为 run.sh, 在里面设置好 `CCNET_CONF_DIR`, `PYTHONPATH` 等。

## 运行

启动 elasticsearch

    cd elasticsearch-bin/elasticsearch/
    bin/elasticsearch

## 更新索引

    ./run.sh --clear # 删除索引
    ./run.sh  # 更新索引


# 测试 #

测试之前先确保本地 elasticsearch 正在运行

* 下载 python-seafile 和 py.test。 py.test 是测试工具， python-seafile 用来作为
测试时修改文件的客户端。

    pip install python-seafile
    pip install pytest==3.1.0 mock==2.0.0 pytest-catchlog==1.2.2

* 设置 `SEAFILE_CONF_DIR` (seafes 需要它来访问 seafile 数据库）

    export SEAFILE_CONF_DIR=/path/to/seafile-data

* 在本地创建一个用户 `test@seafiletest.com`, 密码 `testtest`

* 运行测试:

    pytest
