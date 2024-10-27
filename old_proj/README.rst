|build| |coverage|

FeedProxy
=========

FeedProxy is an app for aggregate posts from RSS feeds to Telegram.

.. contents:: Table of Contents
 :depth: 5

How to use
----------

Setup
~~~~~

1. Create network

.. code-block::

  docker network create -d bridge feed_proxy

2. Run `tg_upload_proxy <https://github.com/yakimka/tg_upload_proxy>`_ for sending large audio

.. code-block::

    docker run --network=feed_proxy --name=tg_upload_proxy --env-file=/root/.tg_upload_proxy.env --restart always -d yakim/tg_upload_proxy

3. Mount app dir and run migrations

.. code-block::

    docker run --rm -v /home/user/feed_proxy:/usr/src/app yakim/feed_proxy feed_proxy_db --db-url sqlite:///./my_feed.db upgrade head

4. Create directory for storing feed_proxy data and create source file

.. code-block::

    mkdir /home/user/feed_proxy
    cp /this/repo/sources.example.ini /home/user/feed_proxy/my_feed.ini
    # edit it
    nano /home/user/feed_proxy/my_feed.ini

5. Run feed_proxy

.. code-block::

    docker run --log-driver=journald --rm --network=feed_proxy --name=feed_proxy --env-file=/root/.feed_proxy.env -v /home/user/feed_proxy:/usr/src/app yakim/feed_proxy feed_proxy my_feed.ini --db-url sqlite:///./my_feed.db --proxy-bot-url http://tg_upload_proxy:8081

Schedule job
~~~~~~~~~~~~

You can use crontab

1. Create script. Example:

.. code-block::

    $ cat /home/user/feed_proxy/run.sh
    #!/bin/bash

    docker run --log-driver=journald \
        --rm --network=feed_proxy \
        --name=feed_proxy \
        --env-file=/root/.feed_proxy.env \
        -v /home/user/feed_proxy:/usr/src/app \
        yakim/feed_proxy \
        feed_proxy my_feed.ini --db-url sqlite:///./my_feed.db --proxy-bot-url http://tg_upload_proxy:8081

2. Now you can add it to crontab with `sudo crontab -e`


View logs
~~~~~~~~~

.. code-block::

    journalctl -u docker CONTAINER_NAME=feed_proxy


.. |build| image:: https://github.com/yakimka/feed_proxy/workflows/build/badge.svg
    :target: https://github.com/yakimka/feed_proxy/actions
.. |coverage| image:: https://codecov.io/gh/yakimka/feed_proxy/branch/master/graph/badge.svg?token=5YNW56XJQT
    :target: https://codecov.io/gh/yakimka/feed_proxy
