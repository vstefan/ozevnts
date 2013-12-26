import re
import sys
import psycopg2
import decimal
import requests
from bs4 import BeautifulSoup
from datetime import datetime

import abc
import libcrawler


class OztixCrawler(libcrawler.ICrawler):

    def createDateTimeFromOzTixEventDateString(self, dateTimeStr):
        """ 
            extracts starting datetime from formats like "Tuesday 31 December 2013  (opening 8:00pm)"
            and "Saturday 04 January 2014 (opening 1pm)"
            and "Tuesday 31 December 2013  to Friday 03 January 2014"
            and "Wednesday 01 January 2014  (opening Midday-10.30pm)"
            and "Saturday 28 December 2013   4.00 PM"
            and "Tuesday 31 December 2013   9:00 PM"
            and "Tuesday 07 January 2014 12:30:00"
        """
        dateTimeStr = dateTimeStr.replace("(opening","")
        dateTimeStr = dateTimeStr.replace(")","")
        dateTimeStr = dateTimeStr.replace("Midday","12:00pm")
        dateTimeStr = dateTimeStr.replace(".",":")
        
        # if there is an end date, delete it
        sepIndex = dateTimeStr.find("to")
        if sepIndex != -1:
            return datetime.strptime(dateTimeStr[0:sepIndex].rstrip(), "%A %d %B %Y")
        else:
            # now check for second type of end date
            sepIndex = dateTimeStr.find("-")
            if sepIndex != -1:
                dateTimeStr = dateTimeStr[0:sepIndex]
                
            # and a third unicode type
            sepIndex = dateTimeStr.find(u"\u2013")
            if sepIndex != -1:
                dateTimeStr = dateTimeStr[0:sepIndex]
        
            # now looks like: "Tuesday 31 December 2013  8:00pm"
            #              or "Tuesday 31 December 2013   9:00 PM"
            #              or "Tuesday 31 December 2013  8pm"
            dateTimeStrTokens = dateTimeStr.split()
            dateTimeStr = dateTimeStrTokens[0].strip() + " " + dateTimeStrTokens[1].strip() + " " + dateTimeStrTokens[2].strip() + " " + dateTimeStrTokens[3].strip() + " " + dateTimeStrTokens[4].strip()
            
            if len(dateTimeStrTokens) == 6:
                dateTimeStr += dateTimeStrTokens[5]
            
            # now looks like: "Tuesday 31 December 2013 8:00pm"
            #              or "Tuesday 31 December 2013 9:00PM"
            #              or "Tuesday 31 December 2013 8pm"
            #              or "Tuesday 07 January 2014 12:30:00"
            sepCount = dateTimeStr.count(":")
            if sepCount == 1:
                return datetime.strptime(dateTimeStr, "%A %d %B %Y %I:%M%p")
            elif sepCount == 2:
                return datetime.strptime(dateTimeStr, "%A %d %B %Y %H:%M:%S")
            else:
                return datetime.strptime(dateTimeStr, "%A %d %B %Y %I%p")
            
    def extractTicketInfo(self, eventInfo, eventPage):
        ticketType           = None
        ticketPrice          = None
        bookingFee           = None
        soldOut              = False
        
        print "Now processing: " + eventInfo.URL
                
        # find <div> with id = "venueInfo"
        soup                = BeautifulSoup(eventPage.text)
        eventSummaryDivTag  = soup.find("div", class_="venueInfo")

        if eventSummaryDivTag:
            # date/time always before this next tag, but sometimes has other tags
            # in front of it, so most reliable way of getting to it is working backwards
            divVenueTag = eventSummaryDivTag.find("div", id="ctl00_ContentPlaceHolder1_WucShowsMain1_WucEventsDetail1_pnl_venue")
            
            if divVenueTag is not None and divVenueTag.previous_sibling is not None and divVenueTag.previous_sibling.previous_sibling is not None: 
                eventInfo.eventDateTime = self.createDateTimeFromOzTixEventDateString(divVenueTag.previous_sibling.previous_sibling.string.strip())
            
        if eventInfo.eventDateTime is None:
            eventInfo.invalid = True
            return
            
        # find <table> with tsClass = "ReserveTable"
        # note: find won't work with "tsClass" specified, only works with "tsclass"
        #       even though in the raw source it shows "tsClass", gets converted
        #       to "tsclass" somewhere in the parsing (can check via print tag)
        ticketTableTag = soup.find("table", attrs={"tsclass":"ReserveTable"})
                
        if ticketTableTag is not None:
            ticketTableRowTags = ticketTableTag.find_all("tr")
                        
            # 1 row for each ticket type
            if ticketTableRowTags is not None and len(ticketTableRowTags) > 0:
                ticketNum = 1
                for ticketTableRowTag in ticketTableRowTags:
                    ticketTableRowTagColumnTags = ticketTableRowTag.find_all("td")
                    
                    # only care about first two columns: {ticket_type, total_price}
                    # oztix doesn't display booking fee, only all-inclusive price
                    if ticketTableRowTagColumnTags is not None: 
                        if len(ticketTableRowTagColumnTags) >= 2 and ticketTableRowTagColumnTags[0].contents[0].string is not None and ticketTableRowTagColumnTags[1].string is not None:
                            ticketType  = ticketTableRowTagColumnTags[0].contents[0].string.strip()               
                            ticketPrice = decimal.Decimal(ticketTableRowTagColumnTags[1].string[4:])
                            bookingFee  = decimal.Decimal(0)
                            
                            if len(ticketTableRowTagColumnTags) >= 3 and ticketTableRowTagColumnTags[2].contents[0].string is not None and ticketTableRowTagColumnTags[2].contents[0].string.lower() == "sold out":
                                soldOut           = True
                            else:   
                                soldOut           = False
                                                                                                                
                            eventInfo.ticketInfoList.append(libcrawler.TicketInfo(ticketNum, ticketType, ticketPrice, bookingFee, soldOut))
                            ticketNum += 1
                        # dont throw an exception here as oztix can place promo crap before and after
                        # each ticket category & price
                        #else:
                        #    raise Exception("Unknown length of ticketTableRowTagColumnTags = " + str(len(ticketTableRowTagColumnTags)))
        else:
            eventInfo.invalid = True
        
        # if this URL had no extracted tickets, add a dummy entry
        # so this URL will be saved and ignored in the future
        if not eventInfo.ticketInfoList:
            eventInfo.invalid = True
    
    # oztix shows everything on one page for each category, no pagination required.
    def extractSubsequentURLs(self, searchResultsSoup, vendorURL):
        return
                        
    def extractNewEvents(self, eventTypeId, knownURLs, searchResultsSoup):
        eventInfoList  = []
         
        stateHeaderDivTags = searchResultsSoup.find_all("div", class_ = "state_header")
        
        if stateHeaderDivTags is not None and len(stateHeaderDivTags) > 0:
            for stateHeaderDivTag in stateHeaderDivTags:
                venueState = stateHeaderDivTag.a["name"]
                
                if venueState is not None and len(venueState) > 0:
                    nextStateHeaderTagFound = False
                    nextDivSibling          = stateHeaderDivTag.find_next_sibling("div")
                    
                    while not nextStateHeaderTagFound:
                        if nextDivSibling is not None and nextDivSibling.get("class") is None and nextDivSibling.get("id") is not None and nextDivSibling["id"] == "gigtable":              
                            searchResultDivTags = nextDivSibling.find_all("div", class_ = "gigname")
                    
                            if searchResultDivTags is not None and len(searchResultDivTags) > 0:
                                for searchResultDivTag in searchResultDivTags:       
                                    URL       = searchResultDivTag.contents[0]["href"]
                                    eventName = searchResultDivTag.contents[0].string
                                    
                                    if URL is None or eventName is None:
                                        raise Exception("Failed to read URL or EventName from gigname search results.")
                                    
                                    nextDivSibling = nextDivSibling.find_next_sibling("div")
                                    
                                    if URL is not None and eventName is not None and URL not in knownURLs:
                                        eventInfo = libcrawler.EventInfo(self.vendorId, eventTypeId, eventName, URL)
                                        eventInfo.venueState = venueState
                                                              
                                        eventInfoList.append(eventInfo)
                            else:
                                raise Exception("No gigname tags found.")
                        elif nextDivSibling is None or nextDivSibling.get("class") is not None and nextDivSibling["class"][0] == "state_header":
                            nextStateHeaderTagFound = True
                        else:
                            raise Exception("Unknown div tag in gigtable/state_header siblings encountered: " + str(nextDivSibling))
                else:
                    raise Exception("Venue state not found in state_header tag.")
        else:
            raise Exception("No state header tags found.")
                     
        return eventInfoList
    
    def fetchEventURL(self, URL):
        fetched = False
        output  = False

        while not fetched:
            try:
                r1      = requests.get(URL, allow_redirects=False, headers={"User-Agent":"Mozilla/5.0"})
                output  = requests.get(URL, cookies=r1.cookies, headers={"User-Agent":"Mozilla/5.0"})
                fetched = True
            except requests.Timeout, e:
                #timeout, wait 30 seconds and try again
                print "Received timeout, retrying in 30 seconds..."
                time.sleep(30)

        return output
        
    def extractEventAndTicketInfo(self, eventTypeId, knownURLs, searchResultsSoup):    
        super(OztixCrawler, self).extractEventAndTicketInfo(eventTypeId, knownURLs, searchResultsSoup)
     
    def processSearchURL(self, eventTypeId, searchURL, paginatedInd):
        super(OztixCrawler, self).processSearchURL(eventTypeId, searchURL, paginatedInd)
      
    def run(self):
        super(OztixCrawler, self).run()      
        
    @property
    def vendorId(self):
        return 2
        
    @property
    def vendorURL(self):
        return "http://oztix.com.au"
        
        
# for re-testing specific problematic URLs
#oztixCrawler.processSearchURL(1, "http://www.oztix.com.au/OzTix/OzTixEvents/OzTixFestivals/tabid/1100/Default.aspx", False)
