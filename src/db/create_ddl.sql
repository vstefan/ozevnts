-- before running this script must create
-- ozevntsdev and ozevntsapp roles
-- and ozevnts schema owned by ozevntsdev.
-- see superuser.sql script.
--
-- ozevntsdev: connect when doing development,
-- can execute DDLs on ozevnts schema.
-- ozevntsapp: middleware's connection, has
-- restricted privileges.
--
-- This script should be run as ozevntsdev.

--DROP TABLE ozevnts.event_type;

CREATE TABLE ozevnts.event_type
(
  id serial NOT NULL,
  title text NOT NULL,
  CONSTRAINT event_type_pk PRIMARY KEY (id)
)
WITH (
  OIDS=FALSE
);
ALTER TABLE ozevnts.event_type OWNER TO ozevntsdev;
GRANT SELECT, INSERT, UPDATE, DELETE ON ozevnts.event_type TO ozevntsapp;

insert into ozevnts.event_type(title) values('Music & Festivals');
insert into ozevnts.event_type(title) values('Sport');
insert into ozevnts.event_type(title) values('Art & Culture');

 
-- DROP TABLE ozevnts.vendor;

CREATE TABLE ozevnts.vendor
(
  id serial NOT NULL,
  title text NOT NULL,
  url text NOT NULL,
  CONSTRAINT vendor_pk PRIMARY KEY (id)
)
WITH (
  OIDS=FALSE
);
ALTER TABLE ozevnts.vendor OWNER TO ozevntsdev;
GRANT SELECT, INSERT, UPDATE, DELETE ON ozevnts.vendor TO ozevntsapp;
GRANT USAGE ON ozevnts.vendor_id_seq TO ozevntsapp;

insert into ozevnts.vendor(title, url) values('Moshtix', 'http://moshtix.com.au');
insert into ozevnts.vendor(title, url) values('Oztix', 'http://oztix.com.au');
insert into ozevnts.vendor(title, url) values('Ticketmaster', 'http://ticketmaster.com.au');

-- DROP TABLE ozevnts.vendor_event;
CREATE TABLE ozevnts.vendor_event
(
  id serial not null,
  vendor_id integer NOT NULL,
  event_type_id integer NOT NULL,
  event_title text,
  state text,
  event_timestamp timestamp without time zone,
  event_sys_timestamp timestamp without time zone,
  last_refreshed_timestamp timestamp without time zone NOT NULL,
  invalid_ind character(1),
  url text NOT NULL,
  
  CONSTRAINT vendor_event_pk PRIMARY KEY (id),
  CONSTRAINT vendor_event_fk1 FOREIGN KEY (event_type_id)
      REFERENCES ozevnts.event_type (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT vendor_event_fk2 FOREIGN KEY (vendor_id)
      REFERENCES ozevnts.vendor (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT vendor_event_uq1 UNIQUE (url),
  CONSTRAINT vendor_event_uq2 UNIQUE (vendor_id, event_type_id, event_title, state, event_timestamp, invalid_ind, url),
  CONSTRAINT vendor_event_chk1 CHECK (invalid_ind = ANY (ARRAY['Y'::bpchar, NULL::bpchar]))
)WITH (
  OIDS=FALSE
);
ALTER TABLE ozevnts.vendor_event OWNER TO ozevntsdev;
GRANT SELECT, INSERT, UPDATE, DELETE ON ozevnts.vendor_event TO ozevntsapp;
GRANT USAGE ON ozevnts.vendor_event_id_seq TO ozevntsapp;

-- DROP TABLE ozevnts.vendor_event_ticket;
CREATE TABLE ozevnts.vendor_event_ticket
(
  vendor_event_id integer not null,
  ticket_num integer not null,  
  ticket_type text not null,
  ticket_price numeric not null,
  booking_fee numeric not null,
  sold_out_ind character(1),

  CONSTRAINT vendor_event_ticket_pk PRIMARY KEY (vendor_event_id, ticket_num),
  CONSTRAINT vendor_event_ticket_fk1 FOREIGN KEY (vendor_event_id)
      REFERENCES ozevnts.vendor_event (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT vendor_event_ticket_chk1 CHECK (sold_out_ind = ANY (ARRAY['Y'::bpchar, NULL::bpchar]))
)
WITH (
  OIDS=FALSE
);
ALTER TABLE ozevnts.vendor_event_ticket OWNER TO ozevntsdev;
GRANT SELECT, INSERT, UPDATE, DELETE ON ozevnts.vendor_event_ticket TO ozevntsapp;
    
-- DROP TABLE ozevnts.vendor_listing;

CREATE TABLE ozevnts.vendor_listing
(
  vendor_id integer NOT NULL,
  event_type_id integer NOT NULL,
  search_url text NOT NULL,
  paginated_ind character(1),
  CONSTRAINT vendor_listing_pk PRIMARY KEY (vendor_id, event_type_id, search_url),
  CONSTRAINT vendor_listing_fk1 FOREIGN KEY (vendor_id)
      REFERENCES ozevnts.vendor (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT vendor_listing_fk2 FOREIGN KEY (event_type_id)
      REFERENCES ozevnts.event_type (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT vendor_listing_chk1 CHECK (paginated_ind = ANY (ARRAY['Y'::bpchar, NULL::bpchar]))
)
WITH (
  OIDS=FALSE
);
ALTER TABLE ozevnts.vendor_listing OWNER TO ozevntsdev;
GRANT SELECT, INSERT, UPDATE, DELETE ON ozevnts.vendor_listing TO ozevntsapp;

insert into ozevnts.vendor_listing(vendor_id, event_type_id, search_url, paginated_ind) values (1, 1, 'http://www.moshtix.com.au/v2/search?CategoryList=6%2C&Page=1', 'Y');
insert into ozevnts.vendor_listing(vendor_id, event_type_id, search_url, paginated_ind) values (1, 1, 'http://www.moshtix.com.au/v2/search?CategoryList=2%2C&Page=1', 'Y');
insert into ozevnts.vendor_listing(vendor_id, event_type_id, search_url, paginated_ind) values (1, 3, 'http://www.moshtix.com.au/v2/search?CategoryList=3%2C&Page=1', 'Y');
insert into ozevnts.vendor_listing(vendor_id, event_type_id, search_url, paginated_ind) values (1, 3, 'http://www.moshtix.com.au/v2/search?CategoryList=4%2C&Page=1', 'Y');

insert into ozevnts.vendor_listing(vendor_id, event_type_id, search_url, paginated_ind) values (2, 1, 'http://www.oztix.com.au/OzTix/OzTixEvents/OzTixFestivals/tabid/1100/Default.aspx', NULL);
insert into ozevnts.vendor_listing(vendor_id, event_type_id, search_url, paginated_ind) values (2, 2, 'http://www.oztix.com.au/OzTix/OzTixEvents/OzTixSports/tabid/1096/Default.aspx', NULL);
insert into ozevnts.vendor_listing(vendor_id, event_type_id, search_url, paginated_ind) values (2, 3, 'http://www.oztix.com.au/OzTix/OzTixEvents/OzTixArts/tabid/1095/Default.aspx', NULL);
insert into ozevnts.vendor_listing(vendor_id, event_type_id, search_url, paginated_ind) values (2, 3, 'http://www.oztix.com.au/OzTix/OzTixEvents/OztixComedy.aspx', NULL);

insert into ozevnts.vendor_listing(vendor_id, event_type_id, search_url, paginated_ind) values (3, 1, 'http://www.ticketmaster.com.au/json/browse/music', NULL);
insert into ozevnts.vendor_listing(vendor_id, event_type_id, search_url, paginated_ind) values (3, 2, 'http://www.ticketmaster.com.au/json/browse/sports', NULL);
insert into ozevnts.vendor_listing(vendor_id, event_type_id, search_url, paginated_ind) values (3, 3, 'http://www.ticketmaster.com.au/json/browse/arts', NULL);
