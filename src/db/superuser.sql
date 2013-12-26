-- run this as superuser before running
-- create_ddl.sql or create_functions.sql

create role ozevntsdev with login encrypted password 'test';
create role ozevntsapp with login encrypted password 'test';

CREATE SCHEMA ozevnts AUTHORIZATION ozevntsdev;
GRANT ALL ON SCHEMA ozevnts TO ozevntsdev;
GRANT USAGE ON SCHEMA ozevnts TO ozevntsapp;
