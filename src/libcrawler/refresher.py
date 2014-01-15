import gc
import logging
import psycopg2
import libcrawler
import crawlerfactory
from util import dbconnector

#enable for testing memory usage
#from guppy import hpy


def load_events_to_refresh(db_con):
    """ Loads events to refresh. """
    event_info_list = []
    current_event   = None

    with db_con.cursor() as cur1:
        cur1.callproc("ozevnts.get_tickets_to_refresh", ["events_refresh_curname"])

        with db_con.cursor("events_refresh_curname") as cur2:
            for record in cur2:
                new_ticket = libcrawler.TicketInfo(record[4], record[5], record[6], record[7], record[8])

                # first event or new event?
                if current_event is None or current_event.vendor_event_id != record[0]:
                    if current_event is not None:
                        event_info_list.append(current_event)

                    current_event = libcrawler.EventInfo(record[1], None, None, record[3])
                    current_event.vendor_event_id = record[0]
                    current_event.event_datetime  = record[2]

                current_event.ticket_list.append(new_ticket)

            # save last event too
            if current_event is not None:
                event_info_list.append(current_event)

    return event_info_list


def refresh_events(db_con, crawler_fact, events_to_refresh):
    event_ids_to_mark_refreshed = []

    while events_to_refresh:
        event_to_refresh  = events_to_refresh.pop()
        latest_event_data = libcrawler.EventInfo(event_to_refresh.vendor_id, event_to_refresh.event_type_id,
                                                 event_to_refresh.event_name, event_to_refresh.url)
        latest_event_data.vendor_event_id = event_to_refresh.vendor_event_id
        crawler = crawler_fact.get_crawler(event_to_refresh.vendor_id)
        crawler.load_tickets_for_event(latest_event_data)

        existing_num_tickets = len(event_to_refresh.ticket_list)
        new_num_tickets      = len(latest_event_data.ticket_list)

        # don't do this anymore, leave the event as is if marked invalid
        #if latest_event_data.invalid:
        #    latest_event_data.invalidate_event(db_con)
        #    db_con.commit()
        if not latest_event_data.invalid:
            # same number or more ticket types? only update any changes to existing tickets
            if existing_num_tickets == new_num_tickets or new_num_tickets > existing_num_tickets:
                for idx, existing_ticket in enumerate(event_to_refresh.ticket_list):
                    if latest_event_data.ticket_list[idx].has_been_updated(existing_ticket):
                        latest_event_data.ticket_list[idx].update(db_con, latest_event_data.vendor_event_id)
                        db_con.commit()

            # if there were more tickets types, now insert the new ones
            if new_num_tickets > existing_num_tickets:
                for idx in range(existing_num_tickets, new_num_tickets):
                    latest_event_data.ticket_list[idx].create(db_con, latest_event_data.vendor_event_id)
                    db_con.commit()
            # less ticket types? mark any non-existent ones as sold out, unless its ticket master
            # who sometimes shows tickets not available on their website for a period of time
            elif new_num_tickets < existing_num_tickets and crawler.vendor_id != 3:
                for existing_ticket in event_to_refresh.ticket_list:
                    if not existing_ticket.sold_out:
                        found_ticket = None

                        for new_ticket in latest_event_data.ticket_list:
                            if new_ticket.ticket_type == existing_ticket.ticket_type:
                                found_ticket = new_ticket
                                break

                        if found_ticket is None:
                            existing_ticket.sold_out = True
                            existing_ticket.update(db_con, event_to_refresh.vendor_event_id)
                            db_con.commit()
                        elif existing_ticket.has_been_updated(found_ticket):
                            found_ticket.update(db_con, latest_event_data.vendor_event_id)
                            db_con.commit()

            event_ids_to_mark_refreshed.append(latest_event_data.vendor_event_id)

        event_to_refresh  = None
        latest_event_data = None
        gc.collect()

    # now mark all events refreshed
    if event_ids_to_mark_refreshed:
        with db_con.cursor() as cur1:
            cur1.callproc("ozevnts.mark_events_refreshed", [event_ids_to_mark_refreshed])
            db_con.commit()


def run():
    """ Performs one refresh cycle."""
    with psycopg2.connect(dbconnector.DbConnector.get_db_str("util")) as conn:
        crawler_fact = crawlerfactory.CrawlerFactory(conn)

        logging.info("Commencing refresh cycle..")
        events_to_refresh = load_events_to_refresh(conn)
        refresh_events(conn, crawler_fact, events_to_refresh)
        logging.info("Finished refresh cycle, sleeping..")
        #enable for testing memory usage
        #h = hpy()
        #print h.heap()