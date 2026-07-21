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

## Usage

1. Create a folder for configuration files (by default `config`)
   ```bash
   mkdir config
   ```
2. Create a configuration file with arbitrary name (e.g. `config.yaml`). Example:
   ```yaml
   settings:
     log_level: "INFO"
     post_storage: "sqlite"
     outbox_storage: "sqlite"
     sqlite_db: "feed_proxy.db"
     sentry_dsn: "ENV:SENTRY_DSN"
     metrics_client: "prometheus"
   handlers:
     receivers:
       "@myfeed_robot":
         type: "telegram_bot"
         init_options:
           name: "@myfeed_robot"
           token: "ENV:MYFEED_ROBOT_TOKEN"
       my_console_printer:
         type: console_printer
         init_options:
           name: "my_console_printer"
   sources:
     guido-van-rossum-blog:
       fetcher_options:
        url: http://neopythonic.blogspot.com/feeds/posts/default?alt=rss
       fetcher_type: fetch_text
       id: guido-van-rossum-blog
       parser_options: { }
       parser_type: rss
       streams:
        - active: true
          intervals:
            - '*/10 * * * *'
          message_template: '<a href="${url}">${title}</a>


          ${source_hash_tags}

          ${post_hash_tags}

          '
          modifiers: [ ]
          receiver_options:
            chat_id: '-1001234567890'
            disable_link_preview: false
          receiver_type: '@myfeed_robot'
          squash: true
       tags:
        - guido van rossum
        - blog
   ```
3. You can use environment variables in the configuration file.
   For example, you can use `ENV:MYFEED_ROBOT_TOKEN`
   to set the token for the Telegram bot.
4. Also you can use standard yaml anchors to reuse
   the same configuration for different feeds.
5. To debug configuration file, you can use:
   ```bash
   python -m feed_proxy.cli.config
   ```
6. Run the service:
   ```bash
   python -m feed_proxy.cli.run
   ```

## Pre-send processors

Pre-send processors enrich posts (e.g. translation) after they've been deduplicated but before the
message is sent. Unlike `modifiers`, which run on every fetched post (before storage dedup),
processors only run once per new post, so they're a good place for expensive operations like AI
calls.

Add a `pre_send_processors` list to a stream. Each processor writes its result into the post's
`extras`, which are available in `message_template` alongside the post's base fields.

The MVP ships one processor, `llm_prompt`, which runs an arbitrary instruction over a field
through an LLM (currently Google Gemini) — translation, summarization, or anything else you can
phrase as a prompt. It requires the `GEMINI_API_KEY` environment variable to be set.

```yaml
x_prompts:
  translate_uk: &translate_uk |
    Translate the following text to Ukrainian. Output only the translation,
    no explanations.

    Text:
    {source}

streams:
  - receiver_type: telegram
    message_template: '<b>${title_ua}</b>

      ${description_ua}

      ${url}'
    pre_send_processors:
      - type: llm_prompt
        options:
          source_field: title
          target_field: title_ua
          prompt: *translate_uk
      - type: llm_prompt
        options:
          source_field: description
          target_field: description_ua
          prompt: *translate_uk
```

`x_prompts` is not a special config section — it's a plain YAML top-level key used only to define
a reusable `&translate_uk` anchor, so the same prompt can be referenced (`*translate_uk`) from
multiple processors without duplicating the text. The config loader ignores unknown top-level keys.

`llm_prompt` options:

- `source_field` — name of the field to read (checked in `extras` first, then post attributes)
- `target_field` — `extras` key to write the result to
- `prompt` — instruction for the model; must contain the `{source}` placeholder, which is replaced
  with the source text (plain substring replacement, so other `{`/`}` in the prompt or in the
  source text are left untouched)
- `on_error_value` — value written to `target_field` if the call fails; defaults to the
  unprocessed source text (`None`)

Chaining multiple `llm_prompt` processors lets you combine steps — e.g. summarize into
`extras.summary`, then a second processor reads `source_field: summary` to translate it.

## License

[MIT](https://github.com/yakimka/feed_proxy/blob/master/LICENSE)


## Credits

This project was generated with [`yakimka/cookiecutter-pyproject`](https://github.com/yakimka/cookiecutter-pyproject).
