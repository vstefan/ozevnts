-- run this as superuser before running
-- create_ddl.sql or create_functions.sql

create role ozevntsdev with login encrypted password 'test';
create role ozevntsapp with login encrypted password 'test';

create database ozevntsdb with 
    owner            = ozevntsdev
    encoding         = 'UTF8'
    tablespace       = pg_default
    lc_collate       = 'en_AU.UTF-8'
    lc_ctype         = 'en_AU.UTF-8'
    connection limit = -1;

-- reconnect as superuser to ozevntsdb database

CREATE SCHEMA ozevnts AUTHORIZATION ozevntsdev;
GRANT ALL ON SCHEMA ozevnts TO ozevntsdev;
GRANT USAGE ON SCHEMA ozevnts TO ozevntsapp;

-- now connect as ozevntsdev and run the create_ddl.sql and create_functions.sql scripts

