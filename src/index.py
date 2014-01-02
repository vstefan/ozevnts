import re

from flask import Flask, render_template, request
import psycopg2
from libcrawler import libcrawler
from util import dbconnector


def load_events(db_con, stored_proc_name, args):
    event_list    = []
    current_event = None

    with db_con.cursor() as cur1:
        cur1.callproc(stored_proc_name, args)

        with db_con.cursor(args[0]) as cur2:
            for record in cur2:
                new_ticket = libcrawler.TicketInfo(None, unicode(record[3], "utf-8"), record[4], record[5], record[6])

                # first event or new event?
                if current_event is None or current_event.event_name != unicode(record[1], "utf-8"):
                    if current_event is not None:
                        event_list.append(current_event)

                    current_event = libcrawler.EventInfo(None, None, unicode(record[1], "utf-8"), record[8])
                    current_event.vendor_name    = unicode(record[7], "utf-8")
                    current_event.venue_state    = unicode(record[2], "utf-8")
                    current_event.event_datetime = record[0]

                current_event.ticket_list.append(new_ticket)

            # save last event too
            if current_event is not None:
                event_list.append(current_event)

    return event_list


def load_soon_events(db_con):
    """ Loads next weeks events. Used for default homepage listing.  """
    return load_events(db_con, "ozevnts.get_soon_events", ["soon_events_curname"])


def search_events(db_con, query, state, category):
    """ Find events matching name, state and/or category. """
    return load_events(db_con, "ozevnts.find_events", ["find_events_curname", query, state, category])


mobile_user_agent_regex = re.compile(
    r"/Mobile|iP(hone|od|ad)|Android|BlackBerry|IEMobile|Kindle|NetFront|Silk-Accelerated|(hpw|web)OS|Fennec|Minimo|Opera M(obi|ini)|Blazer|Dolfin|Dolphin|Skyfire|Zune/",
    re.I | re.M)


def is_mobile_device(user_agent):
    if mobile_user_agent_regex.search(user_agent):
        return True
    return False


app = Flask(__name__)


@app.route("/")
def render_this_week_events():
    with psycopg2.connect(dbconnector.DbConnector.get_db_str("libcrawler")) as db_con:
        if is_mobile_device(request.user_agent.string):
            return render_template("mobindex.html", event_list=load_soon_events(db_con), selected_event="",
                                   selected_state="All", selected_category=0)
        else:
            return render_template("index.html", event_list=load_soon_events(db_con), selected_event="",
                                   selected_state="All", selected_category=0)


@app.route("/search")
def render_search_results():
    event    = request.args.get("Event")
    state    = request.args.get("State")
    category = request.args.get("Category")

    # provide defaults to prevent malformed request errors if
    # users manually change url
    if event is None:
        event    = ""
    if state is None:
        state    = "All"
    if category is None:
        category = 0

    with psycopg2.connect(dbconnector.DbConnector.get_db_str("libcrawler")) as db_con:
        if is_mobile_device(request.user_agent.string):
            return render_template("mobindex.html", event_list=search_events(db_con, event, state, category),
                                   selected_event=event, selected_state=state, selected_category=category)
        else:
            return render_template("index.html", event_list=search_events(db_con, event, state, category),
                                   selected_event=event, selected_state=state, selected_category=category)


if __name__ == '__main__':
    #app.debug   = True
    app.run(host='0.0.0.0')
