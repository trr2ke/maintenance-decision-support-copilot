FROM apache/age@sha256:cd6e62c12924b0e04f69f5f23326c94a55ac13e77a66c7594da1c4f4328a397d

# PostgreSQL 18.6 / AGE 1.8.0, with the matching PGDG pgvector package.
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-18-pgvector=0.8.6-1.pgdg13+1 \
    && rm -rf /var/lib/apt/lists/*

COPY init-extensions.sql /docker-entrypoint-initdb.d/10-extensions.sql
