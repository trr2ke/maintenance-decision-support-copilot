\set ON_ERROR_STOP on

-- Infrastructure only: application tables and graphs belong to later migrations.
CREATE EXTENSION IF NOT EXISTS age;
CREATE EXTENSION IF NOT EXISTS vector;
