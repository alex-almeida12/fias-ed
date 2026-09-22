#!/bin/bash
# Executado uma única vez pelo entrypoint do PostgreSQL ao criar o volume.
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v db="$POSTGRES_DB" \
  -v migrator_pw="$FIAS_ED_MIGRATOR_PASSWORD" \
  -v app_pw="$FIAS_ED_APP_PASSWORD" <<'SQL'
CREATE ROLE fias_ed_migrator LOGIN PASSWORD :'migrator_pw';
CREATE ROLE fias_ed_app LOGIN PASSWORD :'app_pw';
ALTER DATABASE :"db" OWNER TO fias_ed_migrator;
REVOKE ALL ON DATABASE :"db" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db" TO fias_ed_app;
ALTER SCHEMA public OWNER TO fias_ed_migrator;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO fias_ed_app;
ALTER DEFAULT PRIVILEGES FOR ROLE fias_ed_migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO fias_ed_app;
ALTER DEFAULT PRIVILEGES FOR ROLE fias_ed_migrator IN SCHEMA public
  GRANT USAGE ON SEQUENCES TO fias_ed_app;
SQL
