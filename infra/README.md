# Local readiness infrastructure

Run commands from the repository root. This stack supplies infrastructure only;
it does not create application tables, ingest kit records, or implement an agent.
The supplied kit stays local and is mounted read-only, never copied into an image.
Set `KIT_DIR` in the root `.env` to an absolute local directory if the kit is not
at `./rtx-ai-session-kit`. Keep `.env` and the kit out of Git.

```powershell
docker compose -f compose.yaml config --quiet
docker compose -f compose.yaml up -d --build --wait --wait-timeout 180
docker compose -f compose.yaml ps
Get-Content -Raw infra/postgres/verify-extensions.sql | docker compose -f compose.yaml exec -T postgres psql -U agent -d agent
```

Check `$LASTEXITCODE` after each native command; stop if it is nonzero. The SQL
probe exercises Cypher and vector distance and rolls back its temporary graph.
Expected values are Cypher result `2`, cosine distance `0`, and
`probe_rolled_back = t`.

| Service | Host endpoint | Pinned runtime |
| --- | --- | --- |
| PostgreSQL | `postgresql://agent:agent@localhost:5432/agent` | PostgreSQL 18.6, AGE 1.8.0, pgvector 0.8.6 |
| Phoenix | `http://localhost:6006` | 20.23.0 |
| Parts API | `http://localhost:8085` | Python 3.12.13, original local kit server |

All host ports bind to `127.0.0.1`. These are local development credentials.
Phoenix receives OTLP/HTTP traces at `http://localhost:6006/v1/traces`; gRPC port
4317 is not published. Service health checks do not prove trace ingestion or
parts-query correctness during injected faults; application acceptance covers
those separately. Phoenix can take approximately 30 seconds to initialize.

The project is named `maintenance-copilot-readiness`. PostgreSQL persists in the
named `maintenance-copilot-readiness_pgdata` volume mounted at
`/var/lib/postgresql`; PGDATA is `/var/lib/postgresql/18/docker`. Phoenix persists
its local SQLite database under `/phoenix-data` in its own named volume.
PostgreSQL init SQL enables only `age` and `vector`, and runs only for a new
database volume. Existing volumes need deliberate migrations; editing init SQL
does not update them.

To stop without removing state:

```powershell
docker compose -f compose.yaml stop
```

The verified cluster and extension identities survived both a restart and
recreation of this stack's PostgreSQL container while retaining its named volume:

```powershell
docker compose -f compose.yaml up --force-recreate --no-deps -d --wait postgres
```

Before and after recreation, the cluster identifier was `7699145168294301739`,
with extension OIDs `age=16386`, `vector=17039`, and `plpgsql=13643`. The extension
probe then returned Cypher result `2`, vector distance `0`, and successful graph
rollback. The PostgreSQL named-volume mount was inspected; no volumes were
deleted, and other service containers were not recreated. These identifiers are
evidence for this local verification, not values required on a fresh installation.

The AGE base, Phoenix and Python images are pinned by registry digest in the
Dockerfile/Compose file. The PGDG pgvector package is pinned to
`0.8.6-1.pgdg13+1`; building still requires that package to remain available from
PGDG. The built database image remains local. Update pins deliberately and rerun
the extension probe before accepting a replacement.

Primary references used for configuration:

- [PostgreSQL image documentation: PostgreSQL 18 volume layout](https://github.com/docker-library/docs/blob/master/postgres/README.md)
- [pgvector: PostgreSQL APT package installation](https://github.com/pgvector/pgvector#apt)
- [Phoenix container implementation](https://github.com/Arize-ai/phoenix/blob/main/Dockerfile)
- [Phoenix published image tags](https://hub.docker.com/r/arizephoenix/phoenix/tags)
