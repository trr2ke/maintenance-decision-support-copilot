\set ON_ERROR_STOP on

SELECT current_setting('server_version') AS postgres_version;
SELECT extname, extversion FROM pg_extension WHERE extname IN ('age', 'vector') ORDER BY extname;
SELECT current_setting('data_directory') AS data_directory;
SELECT system_identifier FROM pg_control_system();

BEGIN;
LOAD 'age';
SET LOCAL search_path = ag_catalog, public;
SELECT create_graph('readiness_probe');
SELECT * FROM cypher('readiness_probe', $$RETURN 1 + 1 AS result$$) AS (result agtype);
SELECT '[1,0,0]'::vector <=> '[1,0,0]'::vector AS identical_vector_cosine_distance;
ROLLBACK;

-- The graph probe must not leave application objects behind.
SELECT count(*) = 0 AS probe_rolled_back FROM ag_catalog.ag_graph WHERE name = 'readiness_probe';
