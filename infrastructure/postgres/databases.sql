-- Do not repurpose an existing privileged role or one with inherited memberships.
SELECT NOT EXISTS (
    SELECT 1 FROM pg_roles r
    WHERE r.rolname IN (:'core_user', :'notifications_user')
      AND (r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls
           OR EXISTS (SELECT 1 FROM pg_auth_members m WHERE m.member = r.oid))
) AS roles_are_safe \gset
\if :roles_are_safe
\else
    \echo 'Refusing to repurpose privileged application roles or role memberships'
    \quit 3
\endif

SELECT format('CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS', :'core_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'core_user') \gexec
SELECT format('CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS', :'notifications_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'notifications_user') \gexec
SELECT format('ALTER ROLE %I LOGIN PASSWORD %L', :'core_user', :'core_password') \gexec
SELECT format('ALTER ROLE %I LOGIN PASSWORD %L', :'notifications_user', :'notifications_password') \gexec

-- CREATE DATABASE must run outside a transaction; repeated bootstrap preserves rows.
SELECT format('CREATE DATABASE %I OWNER %I', :'core_db', :'core_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'core_db') \gexec
SELECT format('CREATE DATABASE %I OWNER %I', :'notifications_db', :'notifications_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'notifications_db') \gexec

BEGIN;
SELECT format('ALTER DATABASE %I OWNER TO %I', :'core_db', :'core_user') \gexec
SELECT format('ALTER DATABASE %I OWNER TO %I', :'notifications_db', :'notifications_user') \gexec
SELECT format('REVOKE ALL ON DATABASE %I FROM PUBLIC', :'core_db') \gexec
SELECT format('REVOKE ALL ON DATABASE %I FROM PUBLIC', :'notifications_db') \gexec
SELECT format('REVOKE ALL ON DATABASE %I FROM %I', :'core_db', :'notifications_user') \gexec
SELECT format('REVOKE ALL ON DATABASE %I FROM %I', :'notifications_db', :'core_user') \gexec
SELECT format('GRANT CONNECT, TEMPORARY ON DATABASE %I TO %I', :'core_db', :'core_user') \gexec
SELECT format('GRANT CONNECT, TEMPORARY ON DATABASE %I TO %I', :'notifications_db', :'notifications_user') \gexec
COMMIT;
