import re

from flask import Flask, render_template, request
from datetime import datetime
import psycopg2
from libcrawler import libcrawler
        

def loadEvents(dbCon, storedProcName, args):
    eventInfoList = []
    currentEvent  = None

    with dbCon.cursor() as cur1:
        cur1.callproc(storedProcName, args)

        with dbCon.cursor(args[0]) as cur2:
            for record in cur2:
                newTicket = libcrawler.TicketInfo(None, unicode(record[3], "utf-8"), record[4], record[5], record[6])

                # first event or new event?
                if currentEvent is None or currentEvent.eventName != unicode(record[1], "utf-8"):
                    if currentEvent is not None:
                        eventInfoList.append(currentEvent)

                    currentEvent = libcrawler.EventInfo(None, None, unicode(record[1], "utf-8"), record[8])
                    currentEvent.vendorName    = unicode(record[7], "utf-8")
                    currentEvent.venueState    = unicode(record[2], "utf-8")
                    currentEvent.eventDateTime = record[0]

                currentEvent.ticketInfoList.append(newTicket)
         
            # save last event too
            if currentEvent is not None:
                eventInfoList.append(currentEvent)

    return eventInfoList

def loadSoonEvents(dbCon):
    """ Loads next weeks events. Used for default homepage listing.  """
    return loadEvents(dbCon, "ozevnts.get_soon_events", ["soon_events_curname"])
    
def searchEvents(dbCon, query, state, category):
    """ Find events matching name, state and/or category. """
    return loadEvents(dbCon, "ozevnts.find_events", ["find_events_curname", query, state, category])

mobileUserAgentReg = re.compile(r"/Mobile|iP(hone|od|ad)|Android|BlackBerry|IEMobile|Kindle|NetFront|Silk-Accelerated|(hpw|web)OS|Fennec|Minimo|Opera M(obi|ini)|Blazer|Dolfin|Dolphin|Skyfire|Zune/", re.I|re.M)

def isMobileDevice(userAgent):
    if mobileUserAgentReg.search(userAgent):
        return True
    return False


app = Flask(__name__)

@app.route("/")
def render_this_week_events():
    with psycopg2.connect(database="ozevntsdb", user="ozevntsapp", password="test") as dbCon:
        if isMobileDevice(request.user_agent.string):
            return render_template("mobindex.html", eventInfo=loadSoonEvents(dbCon), selectedEvent="", selectedState="All", selectedCategory=0)
        else:
            return render_template("index.html", eventInfo=loadSoonEvents(dbCon), selectedEvent="", selectedState="All", selectedCategory=0)
        
@app.route("/search")
def render_search_results():
    event    = request.args.get("Event")
    state    = request.args.get("State")
    category = request.args.get("Category")
    
    # provide defaults to prevent malformed request errors if
    # users manually change URL
    if event is None:
        event    = ""
    if state is None:
        state    = "All"
    if category is None:
        category = 0
    
    with psycopg2.connect(database="ozevntsdb", user="ozevntsapp", password="test") as dbCon:
        if isMobileDevice(request.user_agent.string):
            return render_template("mobindex.html", eventInfo=searchEvents(dbCon, event, state, category), selectedEvent=event, selectedState=state, selectedCategory=category)    
        else:
            return render_template("index.html", eventInfo=searchEvents(dbCon, event, state, category), selectedEvent=event, selectedState=state, selectedCategory=category)    


if __name__ == '__main__':
    app.run(host='0.0.0.0')
    
