BEGIN;
SELECT format('ALTER SCHEMA public OWNER TO %I', :'app_user') \gexec
REVOKE ALL ON SCHEMA public FROM PUBLIC;
SELECT format('GRANT USAGE, CREATE ON SCHEMA public TO %I', :'app_user') \gexec

-- Only known application/migration tables; do not REASSIGN OWNED cluster-wide.
-- ALTER OWNER preserves rows, IDs, constraints and index definitions.
SELECT format('ALTER TABLE public.%I OWNER TO %I', c.relname, :'app_user')
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r'
  AND c.relname IN ('events', 'registrations', 'email_outbox', 'notification_jobs', 'alembic_version')
ORDER BY c.relname \gexec
COMMIT;
