import re
import sys
import psycopg2
import decimal
from bs4 import BeautifulSoup
from datetime import datetime

import abc
import libcrawler


class MoshtixCrawler(libcrawler.ICrawler):

    def createDateTimeFromMoshTixString(self, dateTimeStr, monthFormatMask):
        """
            MoshTix uses multiple formats (short & long) for month display.
        """
        dateTimeStrTokens   = dateTimeStr.split(",")
        dayMonthTokens      = dateTimeStrTokens[1].lstrip().split(" ")
            
        filteredDateTimeStr = dateTimeStrTokens[0] + " " + dayMonthTokens[1][0:len(dayMonthTokens[1])-2] + " " + dayMonthTokens[2] + " " + dateTimeStrTokens[2].lstrip()
        
        return datetime.strptime(filteredDateTimeStr, "%I:%M%p %d " + monthFormatMask + " %Y")

    def createDateTimeFromMoshTixEventDateString(self, dateTimeStr):
        """ 
            extracts starting datetime from formats like "5:00pm, Fri 4th October, 2013"
            and ""9:00pm, Fri 20th December, 2013 - 4:00am, Sat 28th December, 2013" 
        """
        sepIndex = dateTimeStr.find("-")
        if sepIndex != -1:
            return self.createDateTimeFromMoshTixString(dateTimeStr[0:sepIndex-1], "%B")
        else:
            return self.createDateTimeFromMoshTixString(dateTimeStr, "%B")
            
    def extractTicketInfo(self, eventInfo, eventPage):
        ticketType           = None
        ticketPrice          = None
        bookingFee           = None
        soldOut              = False
        
        print "Now processing: " + eventInfo.URL
                
        # find <div> with id = "event-summary-block"
        soup                = BeautifulSoup(eventPage.text)
        eventSummaryDivTag  = soup.find("div", id="event-summary-block")

        if eventSummaryDivTag is not None:        
            eventInfo.eventDateTime = self.createDateTimeFromMoshTixEventDateString(eventSummaryDivTag["data-event-date"])
            venueTokens   = eventSummaryDivTag["data-event-venue"].split(",") 
            
            # format examples: "Enigma Bar, SA"
            #                : "Candy's Apartment, Kings Cross, NSW"
            #                : "Duke of Wellington, 146 Flinders St, Melbourne, VIC"
            if len(venueTokens) >= 2:
                eventInfo.venueName  = venueTokens[0]
                eventInfo.venueState = venueTokens[len(venueTokens)-1].lstrip()
        
        if eventInfo.eventDateTime is None:
            raise Exception("Failed to parse event date/time from: " + eventInfo.URL)

        if eventInfo.venueState is None:
            raise Exception("Failed to parse venue state from: " + eventInfo.URL)
            
        # find <table> with id = "event-tickettypetable"
        ticketTableTag = soup.find("table", id="event-tickettypetable")
        
        if ticketTableTag is not None:
            ticketTableBodyTag = ticketTableTag.find("tbody")
            
            if ticketTableBodyTag is not None:
                ticketTableRowTags = ticketTableBodyTag.find_all("tr")
                
                # 1 row for each ticket type
                if ticketTableRowTags is not None and len(ticketTableRowTags) > 0:
                    ticketNum = 1
                    for ticketTableRowTag in ticketTableRowTags:
                        ticketTableRowTagColumnTags = ticketTableRowTag.find_all("td")
                        
                        # each ticket type should have 6 columns (ticket type, sale date, ticket price, booking fee, total price, amount of tickets or sold out)
                        if ticketTableRowTagColumnTags is not None: 
                            if len(ticketTableRowTagColumnTags) == 7:
                                ticketType  = ticketTableRowTagColumnTags[0].contents[2].string.strip()                                
                                ticketPrice = decimal.Decimal(ticketTableRowTagColumnTags[2].string[1:].replace(",",""))
                                bookingFee  = decimal.Decimal(ticketTableRowTagColumnTags[4].string[1:].replace(",",""))
                                
                                if len(ticketTableRowTagColumnTags[6].contents) == 1:
                                    ticketSellingStr = ticketTableRowTagColumnTags[6].string.strip()
                                
                                    if ticketSellingStr.lower() == "allocation exhausted":
                                        soldOut = True
                                
                                eventInfo.ticketInfoList.append(libcrawler.TicketInfo(ticketNum, ticketType, ticketPrice, bookingFee, soldOut))
                                ticketNum += 1
                            else:
                                raise Exception("Unknown length of ticketTableRowTagColumnTags = " + str(len(ticketTableRowTagColumnTags)))
        else:
            eventInfo.invalid = True
        
        # if this URL had no extracted tickets, add a dummy entry
        # so this URL will be saved and ignored in the future
        if not eventInfo.ticketInfoList:
            eventInfo.invalid = True
    
    def extractSubsequentURLs(self, searchResultsSoup, vendorURL):
        subsequentURLs = []
        paginationTag  = searchResultsSoup.find("section", class_ = "pagination")
        
        if paginationTag is not None:
            ahrefTags = paginationTag.find_all("a")
            
            if ahrefTags is not None and len(ahrefTags) > 0:
                for ahrefTag in ahrefTags:
                    if len(ahrefTag["href"]) > 0 and "class" not in ahrefTag:
                        subsequentURLs.append(vendorURL + ahrefTag["href"])
                    
        return subsequentURLs
                        
    def extractNewEvents(self, eventTypeId, knownURLs, searchResultsSoup):
        eventInfoList  = []
                
        searchResultDivTags = searchResultsSoup.find_all("div", {"class":"searchresult_content"})
        
        if searchResultDivTags is not None and len(searchResultDivTags) > 0:
            for searchResultDivTag in searchResultDivTags:            
                URL       = searchResultDivTag.contents[1]["href"]
                eventName = searchResultDivTag.contents[3].contents[0].string

                if URL is not None and eventName is not None and URL not in knownURLs:
                    eventInfoList.append(libcrawler.EventInfo(self.vendorId, eventTypeId, eventName, URL))
        else:
            raise Exception("No searchresult_content div tags found.")
            
        return eventInfoList

    def fetchEventURL(self, URL):
        return super(MoshtixCrawler, self).fetchEventURL(URL)
    
    def extractEventAndTicketInfo(self, eventTypeId, knownURLs, searchResultsSoup):    
        super(MoshtixCrawler, self).extractEventAndTicketInfo(eventTypeId, knownURLs, searchResultsSoup)
     
    def processSearchURL(self, eventTypeId, searchURL, paginatedInd):
        super(MoshtixCrawler, self).processSearchURL(eventTypeId, searchURL, paginatedInd)
     
    def run(self):
        super(MoshtixCrawler, self).run()
        
    @property
    def vendorId(self):
        return 1
        
    @property
    def vendorURL(self):
        return "http://moshtix.com.au"
        

# for re-testing specific problematic URLs
#moshtixCrawler.processSearchURL(3, " http://moshtix.com.au/v2/search?CategoryList=3%2C&Page=5", False)
