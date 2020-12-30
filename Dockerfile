### Development image ###
FROM python:3.8 as development

ARG SKIP_TEST

WORKDIR /code

RUN pip install --upgrade pip
# Copy requirements and install it for caching
COPY requirements.txt requirements.dev.txt /
# Install production requirements in prefix for use in production image
RUN pip install -r /requirements.txt --no-warn-script-location --prefix=/install && \
    # copy requirements to /usr/local and then install dev-requirements to handle conflicts
    cp -r /install/* /usr/local && \
    pip install -r /requirements.dev.txt --no-warn-script-location

COPY . .
# Install app in prefix for use in production image
RUN pip install . --no-warn-script-location --no-deps --prefix=/install

# Install app in editable mode for development
# without dependencies, because they were installed in the previous steps
RUN pip install -e '.[dev]' --no-deps

# Run tests
RUN if [ -z "$SKIP_TEST" ] ; then \
        make lint && make test ; \
    else echo "skip tests and linter" ; fi

### Production image ###
FROM python:3.8-slim as production

# Copy installed packages to /usr/local
COPY --from=development /install /usr/local

RUN groupadd -r feed_proxy && \
    useradd -r -g feed_proxy feed_proxy -m --uid 1000 && \
    mkdir -p /usr/src/app && \
    chown feed_proxy:feed_proxy /usr/src/app

WORKDIR /usr/src/app

USER feed_proxy
