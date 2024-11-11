# FeedProxy

[![Build Status](https://github.com/yakimka/feed_proxy/actions/workflows/workflow-ci.yml/badge.svg?branch=master&event=push)](https://github.com/yakimka/feed_proxy/actions/workflows/workflow-ci.yml)
[![Codecov](https://codecov.io/gh/yakimka/feed_proxy/branch/master/graph/badge.svg)](https://codecov.io/gh/yakimka/feed_proxy)
[![PyPI - Version](https://img.shields.io/pypi/v/feed_proxy.svg)](https://pypi.org/project/feed_proxy/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/feed_proxy)](https://pypi.org/project/picodi/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/feed_proxy)](https://pypi.org/project/picodi/)

FeedProxy is an app for aggregate posts from feeds (rss, web pages, etc.) to Telegram or other services.

<details>
<summary>History</summary>

This project was created to solve the problem of aggregating posts from different sources to Telegram.
In first iteration, it was script that was running on my server and sending posts to Telegram.

After some time, I decided to make it more flexible and created a web service that
can be used by anyone - [Feed Watchdog](https://github.com/yakimka/feed_watchdog/).

But then i realized that i don't need all this complexity and decided to
reimplement it like a library from first iteration but with improvements that i got from
the second iteration.

</details>

## License

[MIT](https://github.com/yakimka/feed_proxy/blob/master/LICENSE)


## Credits

This project was generated with [`yakimka/cookiecutter-pyproject`](https://github.com/yakimka/cookiecutter-pyproject).
