-- Role só de leitura para a API (a API nunca escreve; o batch usa o dono do banco).
-- Idempotente: pode rodar a cada subida. Uso (a senha vem de fora, nunca neste arquivo):
--   psql -v ON_ERROR_STOP=1 -v pw="$READONLY_POSTGRES_PASSWORD" -f database/readonly_role.sql <URL do dono>
-- Os privilégios padrão cobrem tabelas criadas depois (migrações rodadas pelo dono).
SELECT format('CREATE ROLE finance_ro LOGIN PASSWORD %L', :'pw')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'finance_ro') \gexec

ALTER ROLE finance_ro WITH LOGIN PASSWORD :'pw' NOSUPERUSER NOCREATEDB NOCREATEROLE;
ALTER ROLE finance_ro SET default_transaction_read_only = on;

SELECT format('GRANT CONNECT ON DATABASE %I TO finance_ro', current_database()) \gexec
GRANT USAGE ON SCHEMA public TO finance_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO finance_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO finance_ro;
