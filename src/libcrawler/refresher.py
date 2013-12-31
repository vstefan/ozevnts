import time
import psycopg2
import libcrawler
import crawlerfactory
import gc

#enable for testing memory usage
#from guppy import hpy

def loadEventsToRefresh(dbCon):
    """ Loads events to refresh. """
    eventInfoList = []
    currentEvent  = None
    
    with dbCon.cursor() as cur1:
        cur1.callproc("ozevnts.get_tickets_to_refresh", ["events_refresh_curname"])
        
        with dbCon.cursor("events_refresh_curname") as cur2:
            for record in cur2:
                newTicket = libcrawler.TicketInfo(record[4], record[5], record[6], record[7], record[8])
            
                # first event or new event?
                if currentEvent is None or currentEvent.vendorEventId != record[0]:
                    if currentEvent is not None:
                        eventInfoList.append(currentEvent)
                    
                    currentEvent = libcrawler.EventInfo(record[1], None, None, record[3])
                    currentEvent.vendorEventId = record[0]
                    currentEvent.eventDateTime = record[2]
            
                currentEvent.ticketInfoList.append(newTicket)
            
            # save last event too
            if currentEvent is not None:
                eventInfoList.append(currentEvent)
                    
    return eventInfoList
    
    
def refreshEvents(dbCon, crawlerFact, eventsToRefresh):
    eventIdsToMarkRefreshed = []

    for eventToRefresh in eventsToRefresh:    
        latestEventData = libcrawler.EventInfo(eventToRefresh.vendorId, eventToRefresh.eventTypeId, eventToRefresh.eventName, eventToRefresh.URL)
        latestEventData.vendorEventId = eventToRefresh.vendorEventId
        crawler         = crawlerFact.getCrawler(eventToRefresh.vendorId)
        crawler.loadTicketsForEvent(latestEventData)
        
        existingNumTickets = len(eventToRefresh.ticketInfoList)
        newNumTickets      = len(latestEventData.ticketInfoList)
        
        if latestEventData.invalid:
            latestEventData.invalidateEvent(dbCon)
            dbCon.commit()
        else:
            # same number or more ticket types? only update any changes to existing tickets
            if existingNumTickets == newNumTickets or newNumTickets > existingNumTickets:
                for idx, existingTicket in enumerate(eventToRefresh.ticketInfoList):
                    if latestEventData.ticketInfoList[idx].hasBeenUpdated(existingTicket):
                        latestEventData.ticketInfoList[idx].update(dbCon, latestEventData.vendorEventId)
                        dbCon.commit()

            # if there were more tickets types, now insert the new ones
            if newNumTickets > existingNumTickets:
                for idx in range(existingNumTickets, newNumTickets):
                    latestEventData.ticketInfoList[idx].create(dbCon, latestEventData.vendorEventId)
                    dbCon.commit()
            # less ticket types? mark any non-existent ones as sold out
            elif newNumTickets < existingNumTickets:
                for existingTicket in eventToRefresh.ticketInfoList:
                    if not existingTicket.soldOut:
                        foundTicket = None


                        for newTicket in latestEventData.ticketInfoList:
                            if newTicket.ticketType == existingTicket.ticketType:
                                foundTicket = newTicket
                                break

                        if foundTicket is None:
                            existingTicket.soldOut = True
                            existingTicket.update(dbCon, eventToRefresh.vendorEventId)
                            dbCon.commit()
                        elif existingTicket.hasBeenUpdated(foundTicket):
                            foundTicket.update(dbCon, latestEventData.vendorEventId)
                            dbCon.commit()

            eventIdsToMarkRefreshed.append(latestEventData.vendorEventId)

    # now mark all events refreshed
    if eventIdsToMarkRefreshed:
        with dbCon.cursor() as cur1:
            cur1.callproc("ozevnts.mark_events_refreshed", [eventIdsToMarkRefreshed])
            dbCon.commit()
            eventIdsToMarkRefreshed = None
           
# refresher execution starts here
conn = psycopg2.connect(database="ozevntsdb", user="ozevntsapp", password="test")
crawlerFact = crawlerfactory.CrawlerFactory(conn)

while True:
    eventsToRefresh = loadEventsToRefresh(conn)
    refreshEvents(conn, crawlerFact, eventsToRefresh)
    eventsToRefresh = None
    gc.collect()
    #enable for testing memory usage
    #h = hpy()
    #print h.heap()
    time.sleep(60*20)
