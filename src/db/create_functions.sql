-- before running this script must create
-- ozevntsdev and ozevntsapp roles
-- and ozevnts schema owned by ozevntsdev.
-- see superuser.sql script.
--
-- ozevntsdev: connect when doing development,
-- can execute DDLs on ozevnts schema.
-- ozevntsapp: middleware's connection, only
-- has execute privileges on stored function API.
--
-- This script should be run as ozevntsdev.

CREATE OR REPLACE FUNCTION ozevnts.array_to_set(
    p_array anyarray
) RETURNS SETOF anyelement AS $$
BEGIN
    FOR idx IN array_lower(p_array, 1)..array_upper(p_array, 1) LOOP
        RETURN NEXT p_array[idx];
    END LOOP;
END;
$$ LANGUAGE plpgsql;
ALTER FUNCTION ozevnts.array_to_set(anyarray) OWNER TO ozevntsdev; 
GRANT EXECUTE ON FUNCTION ozevnts.array_to_set(anyarray) TO ozevntsapp;
  

CREATE OR REPLACE FUNCTION ozevnts.get_tickets_to_refresh(refcursor)
  RETURNS refcursor AS
$BODY$
BEGIN
    open $1 for 
    select ve.id
          ,ve.vendor_id
          ,ve.event_timestamp
          ,ve.url
          ,vet.ticket_num
          ,vet.ticket_type
          ,vet.ticket_price
          ,vet.booking_fee
          ,vet.sold_out_ind
    from  ozevnts.vendor_event ve, ozevnts.vendor_event_ticket vet
    where ve.invalid_ind is null
      and ve.event_sys_timestamp > current_timestamp 
      and (
          (-- event in the next 24 hours? refresh every 60 minutes
           event_sys_timestamp - current_timestamp <= interval '1 day'
       and current_timestamp - last_refreshed_timestamp >= interval '60 minutes'
           ) or
          (-- event in next 24->48 hours? refresh every 4 hours
           event_sys_timestamp - current_timestamp > interval '1 day'
       and event_sys_timestamp - current_timestamp <= interval '2 days'
       and current_timestamp - last_refreshed_timestamp >= interval '4 hours'
           ) or
          (-- event in 48->96 hours? refresh every 12 hours
           event_sys_timestamp - current_timestamp > interval '2 days'
       and event_sys_timestamp - current_timestamp <= interval '4 days'
       and current_timestamp - last_refreshed_timestamp >= interval '12 hours'
           ) or
          (-- event in >96 hours? refresh every day
           event_sys_timestamp - current_timestamp > interval '4 days'
       and current_timestamp - last_refreshed_timestamp >= interval '1 day'
           )
          )
       and vet.vendor_event_id = ve.id;
                    
    return $1;
END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100;
ALTER FUNCTION ozevnts.get_tickets_to_refresh(refcursor) OWNER TO ozevntsdev;
GRANT EXECUTE ON FUNCTION ozevnts.get_tickets_to_refresh(refcursor) TO ozevntsapp;


CREATE OR REPLACE FUNCTION ozevnts.get_known_urls(refcursor, p_vendor_id integer )
  RETURNS refcursor AS
$BODY$
BEGIN
    open $1 for
    select url
    from ozevnts.vendor_event
    where vendor_id = p_vendor_id;

    return $1;
END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100;
ALTER FUNCTION ozevnts.get_known_urls(refcursor, integer)
  OWNER TO ozevntsdev;
GRANT EXECUTE ON FUNCTION ozevnts.get_known_urls(refcursor, integer) TO ozevntsapp;
  
  
CREATE OR REPLACE FUNCTION ozevnts.get_search_urls(refcursor, p_vendor_id integer)
  RETURNS refcursor AS
$BODY$
BEGIN
    open $1 for
    select *    
    from ozevnts.vendor_listing
    where vendor_id = p_vendor_id;

    return $1;
END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100;
ALTER FUNCTION ozevnts.get_search_urls(refcursor, integer) OWNER TO ozevntsdev;
GRANT EXECUTE ON FUNCTION ozevnts.get_search_urls(refcursor, integer) TO ozevntsapp;
  
  
CREATE OR REPLACE FUNCTION ozevnts.create_event(
    p_vendor_id            integer
   ,p_event_type_id        integer
   ,p_event_title          text
   ,p_state                text
   ,p_event_timestamp      timestamp without time zone
   ,p_invalid_ind          character
   ,p_url                  text
)
  RETURNS integer AS
$BODY$
DECLARE
    l_id integer;
BEGIN
    insert into ozevnts.vendor_event(
        vendor_id
       ,event_type_id
       ,event_title
       ,state
       ,event_timestamp
       ,event_sys_timestamp
       ,last_refreshed_timestamp
       ,invalid_ind
       ,url
     ) values (
        p_vendor_id
       ,p_event_type_id
       ,p_event_title
       ,p_state
       ,p_event_timestamp
       ,case when p_event_timestamp is null then null else 
            p_event_timestamp at time zone 
            case p_state
                when 'ACT' then 'Australia/Canberra'
                when 'NSW' then 'Australia/NSW'
                when 'QLD' then 'Australia/Queensland'
                when 'SA'  then 'Australia/South'
                when 'TAS' then 'Australia/Tasmania'
                when 'VIC' then 'Australia/Victoria'
                when 'WA'  then 'Australia/West'
            end
        end
       ,current_timestamp
       ,p_invalid_ind
       ,p_url
     )
     returning id
     into l_id;
     
     return l_id;
END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100;
ALTER FUNCTION ozevnts.create_event(integer, integer, text, text, timestamp without time zone, character, text) OWNER TO ozevntsdev;
GRANT EXECUTE ON FUNCTION ozevnts.create_event(integer, integer, text, text, timestamp without time zone, character, text) TO ozevntsapp;
  
  
CREATE OR REPLACE FUNCTION ozevnts.invalidate_event(p_vendor_event_id integer)
  RETURNS void AS
$BODY$
BEGIN
    update ozevnts.vendor_event
    set invalid_ind = 'Y'
       ,last_refreshed_timestamp = current_timestamp
    where id = p_vendor_event_id;

    delete from ozevnts.vendor_event_ticket
    where vendor_event_id = p_vendor_event_id;
END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100;
ALTER FUNCTION ozevnts.invalidate_event(integer) OWNER TO ozevntsdev;
GRANT EXECUTE ON FUNCTION ozevnts.invalidate_event(integer) TO ozevntsapp;
  

CREATE OR REPLACE FUNCTION ozevnts.mark_events_refreshed(p_vendor_event_ids integer[])
  RETURNS void AS
$BODY$
BEGIN
    update ozevnts.vendor_event
    set last_refreshed_timestamp = current_timestamp
    where id in (select * from ozevnts.array_to_set(p_vendor_event_ids));
END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100;
ALTER FUNCTION ozevnts.mark_events_refreshed(integer[]) OWNER TO ozevntsdev;
GRANT EXECUTE ON FUNCTION ozevnts.mark_events_refreshed(integer[]) TO ozevntsapp;
 
 
CREATE OR REPLACE FUNCTION ozevnts.create_ticket(
    p_vendor_event_id      integer
   ,p_ticket_num           integer
   ,p_ticket_type          text
   ,p_ticket_price         numeric
   ,p_booking_fee          numeric
   ,p_sold_out_ind         character
)
  RETURNS void AS
$BODY$
BEGIN
    insert into ozevnts.vendor_event_ticket(
        vendor_event_id
       ,ticket_num
       ,ticket_type
       ,ticket_price
       ,booking_fee
       ,sold_out_ind
    ) values (
        p_vendor_event_id
       ,p_ticket_num
       ,p_ticket_type
       ,p_ticket_price
       ,p_booking_fee
       ,p_sold_out_ind
    );
END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100;
ALTER FUNCTION ozevnts.create_ticket(integer, integer, text, numeric, numeric, character) OWNER TO ozevntsdev;
GRANT EXECUTE ON FUNCTION ozevnts.create_ticket(integer, integer, text, numeric, numeric, character) TO ozevntsapp;

  
CREATE OR REPLACE FUNCTION ozevnts.update_ticket(
    p_vendor_event_id      integer
   ,p_ticket_num           integer
   ,p_ticket_type          text
   ,p_ticket_price         numeric
   ,p_booking_fee          numeric
   ,p_sold_out_ind         character
)
  RETURNS void AS
$BODY$
BEGIN
    update ozevnts.vendor_event_ticket
     set ticket_type  = p_ticket_type
        ,ticket_price = p_ticket_price
        ,booking_fee  = p_booking_fee
        ,sold_out_ind = p_sold_out_ind
      where vendor_event_id = p_vendor_event_id
        and ticket_num      = p_ticket_num;
END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100;
ALTER FUNCTION ozevnts.update_ticket(integer, integer, text, numeric, numeric, character) OWNER TO ozevntsdev;
GRANT EXECUTE ON FUNCTION ozevnts.update_ticket(integer, integer, text, numeric, numeric, character) TO ozevntsapp;
  
  
-- default homepage view: events in next 7 days  
CREATE OR REPLACE FUNCTION ozevnts.get_soon_events(refcursor)
  RETURNS refcursor AS
$BODY$
BEGIN
    open $1 for
    select ve.event_timestamp
          ,ve.event_title
          ,ve.state
          ,vet.ticket_type
          ,vet.ticket_price
          ,vet.booking_fee
          ,vet.sold_out_ind
          ,v.title
          ,ve.url
    from ozevnts.vendor_event ve, ozevnts.vendor v, ozevnts.vendor_event_ticket vet
    where ve.event_sys_timestamp > current_timestamp 
      and ve.event_sys_timestamp - current_timestamp <= interval '7 days'
      and ve.invalid_ind is null
      and ve.vendor_id = v.id
      and vet.vendor_event_id = ve.id
    order by ve.event_timestamp asc, ve.id asc, vet.ticket_num asc;

    return $1;
END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100;
ALTER FUNCTION ozevnts.get_soon_events(refcursor) OWNER TO ozevntsdev;
GRANT EXECUTE ON FUNCTION ozevnts.get_soon_events(refcursor) TO ozevntsapp;

  
CREATE OR REPLACE FUNCTION ozevnts.find_events(refcursor, p_query text, p_state text, p_event_type_id integer)
  RETURNS refcursor AS
$BODY$
BEGIN
    open $1 for
    select ve.event_timestamp
          ,ve.event_title
          ,ve.state
          ,vet.ticket_type
          ,vet.ticket_price
          ,vet.booking_fee
          ,vet.sold_out_ind
          ,v.title
          ,ve.url
    from ozevnts.vendor_event ve, ozevnts.vendor v, ozevnts.vendor_event_ticket vet
    where ve.event_sys_timestamp > current_timestamp
      and ve.invalid_ind is null
      and ve.event_title ilike '%' || p_query || '%'
      and case when p_state = 'All' then ve.state = ve.state else ve.state = p_state end
      and case when p_event_type_id = 0 then ve.event_type_id = ve.event_type_id else ve.event_type_id = p_event_type_id end
      and ve.vendor_id = v.id
      and vet.vendor_event_id = ve.id
    order by ve.event_timestamp asc, ve.id asc, vet.ticket_num asc;   

    return $1;
END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100;
ALTER FUNCTION ozevnts.find_events(refcursor, text, text, integer) OWNER TO ozevntsdev;
GRANT EXECUTE ON FUNCTION ozevnts.find_events(refcursor, text, text, integer) TO ozevntsapp;
