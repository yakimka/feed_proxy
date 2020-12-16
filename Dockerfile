### Builder ###
FROM python:3.8 as builder

WORKDIR /usr/src/app
COPY . .
RUN pip install wheel && pip wheel -r requirements.txt --wheel-dir=./wheels
RUN pip wheel --wheel-dir=./wheels .

### Image ###
FROM python:3.8-slim

ENV PATH /home/feed_proxy/.local/bin:$PATH

COPY --from=builder /usr/src/app/wheels /wheels
RUN pip install --no-index --find-links=/wheels /wheels/*.whl  && rm -rf /wheels

RUN groupadd -r feed_proxy && useradd -r -g feed_proxy feed_proxy -m --uid 1000

RUN mkdir -p /usr/src/app
RUN chown feed_proxy:feed_proxy /usr/src/app

WORKDIR /usr/src/app

USER feed_proxy
