# PostgreSQL with pg_partman and pg_cron
FROM postgres:15-alpine

# Install build dependencies
RUN apk add --no-cache --virtual .build-deps \
    gcc \
    g++ \
    make \
    musl-dev \
    postgresql15-dev \
    clang \
    llvm \
    git \
    && apk add --no-cache \
    postgresql15-contrib \
    && if [ ! -e /usr/bin/clang-19 ]; then ln -s /usr/bin/clang /usr/bin/clang-19 || true; fi \
    && if [ ! -e /usr/lib/llvm19/bin/llvm-lto ]; then mkdir -p /usr/lib/llvm19/bin && ln -s /usr/bin/llvm-lto /usr/lib/llvm19/bin/llvm-lto || true; fi

# Install pg_partman
RUN cd /tmp \
    && git clone https://github.com/pgpartman/pg_partman.git \
    && cd pg_partman \
    && git checkout v4.7.4 \
    && make && make install \
    && cd / && rm -rf /tmp/pg_partman

# Install pg_cron
RUN cd /tmp \
    && git clone https://github.com/citusdata/pg_cron.git \
    && cd pg_cron \
    && git checkout v1.5.2 \
    && make && make install \
    && cd / && rm -rf /tmp/pg_cron

# Clean up build dependencies
RUN apk del .build-deps

# Configure PostgreSQL for pg_cron
RUN echo "shared_preload_libraries = 'pg_cron,pg_partman_bgw'" >> /usr/local/share/postgresql/postgresql.conf.sample \
    && echo "cron.database_name = 'globant_challenge'" >> /usr/local/share/postgresql/postgresql.conf.sample

# Copy initialization script
COPY scripts/init_db.sql /docker-entrypoint-initdb.d/