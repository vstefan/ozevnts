import abc
import time
import requests
import codecs
import gc

from bs4 import BeautifulSoup
#enable for testing memory usage
#from guppy import hpy

class VendorSearchListing:
    """ Vendor data for a event/ticket search listing. """
    def __init__(self, vendorId, eventTypeId, searchURL, paginatedInd):
        self.vendorId     = vendorId
        self.eventTypeId  = eventTypeId
        self.searchURL    = searchURL
        
        if paginatedInd is not None and paginatedInd == "Y":
            self.paginatedInd = True
        else:
            self.paginatedInd = False
            
    def __repr__(self):
        return "vendorId: " + str(self.vendorId) + ", eventTypeId: " + str(self.eventTypeId) + ", searchURL: " + self.searchURL + ", paginatedInd: " + str(self.paginatedInd)

     
class EventInfo:
    """ Event info extracted from search results & event pages or loaded from db. """
    def __init__(self, vendorId, eventTypeId, eventName, URL):
        self.vendorId          = vendorId
        self.eventTypeId       = eventTypeId
        self.eventName         = eventName
        self.URL               = URL
        self.venueName         = None
        self.venueState        = None
        self.eventDateTime     = None
        self.invalid           = None
        self.vendorEventId     = None
        self.ticketInfoList    = []
        
    def invalidDBVal(self):
        if self.invalid:
            return "Y"
        else:
            return None
        
    def __repr__(self):
        return "vendorId: " + str(self.vendorId) +  ", eventTypeId: " + str(self.eventTypeId) + ", eventName: " + self.eventName + ", URL: " + self.URL + ", venueName: " + self.venueName + ", venueState: " + self.venueState + ", eventDateTime: " + str(self.eventDateTime) + ", invalid + " + str(self.invalid) + ", vendorEventId: " + str(self.vendorEventId)
        
    def createEvent(self, dbCon):
        with dbCon.cursor() as cur1:
            cur1.callproc("ozevnts.create_event", [self.vendorId, self.eventTypeId, self.eventName, self.venueState, self.eventDateTime, self.invalidDBVal(), self.URL])
            
            self.vendorEventId = int(cur1.fetchone()[0])
            
    def createTickets(self, dbCon):
        """ Record a list of tickets for this event. """
        if self.vendorEventId is None:
            raise Exception("Invalid VendorEventId; unable to createTickets for eventName: " + self.eventName)
        elif not self.invalid:
            for ticketInfo in self.ticketInfoList:
                ticketInfo.create(dbCon, self.vendorEventId)
        
    def invalidateEvent(self, dbCon):
        """ Updated an event as now being invalid. """
        if self.invalid:
            with dbCon.cursor() as cur1:
                cur1.callproc("ozevnts.invalidate_event", [self.vendorEventId])
                    
        
class TicketInfo:
    """ Ticket info extracted from event page or loaded from db. """
    def __init__(self, ticketNum, ticketType, ticketPrice, bookingFee, soldOut):
        self.ticketNum         = ticketNum
        self.ticketType        = ticketType
        self.ticketPrice       = ticketPrice
        self.bookingFee        = bookingFee
        self.soldOut           = soldOut
            
    def soldOutDBVal(self):
        if self.soldOut:
            return "Y"
        else:
            return None
            
    def hasBeenUpdated(self, newTicketInfo):
        """ Returns true if any details retrieved in a refresh from vendor have changed. """
        return self.ticketType != newTicketInfo.ticketType or self.ticketPrice != newTicketInfo.ticketPrice or self.bookingFee != newTicketInfo.bookingFee or self.soldOut != newTicketInfo.soldOut
        
    def create(self, dbCon, vendorEventId):
        with dbCon.cursor() as cur1:
            cur1.callproc("ozevnts.create_ticket", [vendorEventId, self.ticketNum, self.ticketType, self.ticketPrice, self.bookingFee, self.soldOutDBVal()])
        
    def update(self, dbCon, vendorEventId):
        with dbCon.cursor() as cur1:
            cur1.callproc("ozevnts.update_ticket", [vendorEventId, self.ticketNum, self.ticketType, self.ticketPrice, self.bookingFee, self.soldOutDBVal()])
                        
    def __repr__(self):
        return "ticketNum: " + str(self.ticketNum) + ", ticketType: " + self.ticketType + ", ticketPrice: " + str(self.ticketPrice) + ", bookingFee: " + str(self.bookingFee) + ", soldOut: " + str(self.soldOut)

        
# START - MISC UTILITY FUNCTIONS # 
def fetchURL(URL):
    fetched = False
    output  = None
    
    while not fetched:
        try:
            print "Opening URL: " + URL
            output  = requests.get(URL, headers={"User-Agent":"Mozilla/5.0"})
            fetched = True
        except requests.Timeout, e:
            #timeout, wait 30 seconds and try again
            print "Received timeout, retrying in 30 seconds..."
            time.sleep(30)

    # for debugging raw response data
    #outFile = codecs.open("output.html", "w", "utf-8")
    #outFile.write(output.text)
    #outFile.close()
    
    return output
# START - MISC UTILITY FUNCTIONS # 

        
class ICrawler(object):    
    """ Abstract class which all site-specific crawlers must implement. """    
    __metaclass__ = abc.ABCMeta
    
    def __init__(self, dbCon):
        self.dbCon = dbCon
       
    # START - ABSTRACT METHODS REQUIRING VENDOR-SPECIFIC IMPLEMENTATION #
    @abc.abstractmethod
    def extractNewEvents(self, eventTypeId, knownURLs, searchResultsSoup):
        """ Parses search results to extract basic event info for unknown events. """
        return
        
    @abc.abstractmethod
    def extractTicketInfo(self, eventInfo, eventPage):
        """ Parses event page to extract further event and ticket info. """
        return
    
    @abc.abstractmethod
    def extractSubsequentURLs(self, searchResultsSoup, vendorURL):
        """ Handles pagination from vendor-specific search results. """
        return

    @abc.abstractmethod
    def fetchEventURL(self, URL):
        """ 
            Some vendors do cookie checks with mess redirects which
            require unique handling in vendor-specific implementations.
        """
        return fetchURL(URL) 
        
    @abc.abstractmethod    
    def extractEventAndTicketInfo(self, eventTypeId, knownURLs, searchResultsSoup):
        """ Extracts event & ticket info from retrieved search results. """
        extractedEventInfoList = self.extractNewEvents(eventTypeId, knownURLs, searchResultsSoup)
          
        for extractedEventInfo in extractedEventInfoList:
            eventPage = self.fetchEventURL(extractedEventInfo.URL)
            self.extractTicketInfo(extractedEventInfo, eventPage)
            extractedEventInfo.createEvent(self.dbCon)
            extractedEventInfo.createTickets(self.dbCon)
            
            self.dbCon.commit()
    
    @abc.abstractmethod
    def processSearchURL(self, eventTypeId, searchURL, paginatedInd):
        """ Processes a search URL to extract all event/ticket info. """
        knownURLs         = self.getKnownURLs()
   
        searchResults     = fetchURL(searchURL)
        searchResultsSoup = BeautifulSoup(searchResults.text)
        
        self.extractEventAndTicketInfo(eventTypeId, knownURLs, searchResultsSoup)
        
        if paginatedInd == True:
            for subsequentURL in self.extractSubsequentURLs(searchResultsSoup, self.vendorURL):
                knownURLs         = self.getKnownURLs()
                searchResults     = fetchURL(subsequentURL)
                searchResultsSoup = BeautifulSoup(searchResults.text)
                self.extractEventAndTicketInfo(eventTypeId, knownURLs, searchResultsSoup)

    @abc.abstractmethod 
    def run(self):
        """ Starts crawling. """
        while True:
            vendorSearchURLs = self.getVendorSearchURLs()

            for vendorSearchURL in vendorSearchURLs:
                self.processSearchURL(vendorSearchURL.eventTypeId, vendorSearchURL.searchURL, vendorSearchURL.paginatedInd)
            
            vendorSearchURLs = None
            gc.collect()
            #enable for testing memory usage
            #h = hpy()
            #print h.heap()    
            time.sleep(60*60*4)
    # END - ABSTRACT METHODS REQUIRING VENDOR-SPECIFIC IMPLEMENTATION #
              

    # START - ABSTRACT PROPERTIES REQUIRING VENDOR-SPECIFIC VALUES #
    @abc.abstractproperty
    def vendorId(self):
        """ Vendor specific id. """
        return
        
    @abc.abstractproperty
    def vendorURL(self):
        """ Vendor specific URL. """
        return
    # END - ABSTRACT PROPERTIES REQUIRING VENDOR-SPECIFIC VALUES #
    

    # START - HELPER METHODS #
    def loadTicketsForEvent(self, eventInfo):
        """ Given a EventInfo with a valid URL, loads tickets for that event. """
        eventPage = self.fetchEventURL(eventInfo.URL)
        self.extractTicketInfo(eventInfo, eventPage)
    
    def getKnownURLs(self):
        """ Given a database connection, fetches known URLs. """
        knownUrls = set()

        with self.dbCon.cursor() as cur1:
            cur1.callproc("ozevnts.get_known_urls", ["known_urls_curname", self.vendorId])
            
            with self.dbCon.cursor("known_urls_curname") as cur2:
                for record in cur2:
                    knownUrls.add(record[0])
                        
        return knownUrls

    def getVendorSearchURLs(self):
        """ Given a database connection, fetches vendor search URLs. """
        vendorSearchUrls = []
        
        with self.dbCon.cursor() as cur1:
            cur1.callproc("ozevnts.get_search_urls", ["search_urls_curname", self.vendorId])
            
            with self.dbCon.cursor("search_urls_curname") as cur2:
                for record in cur2:
                    #print record
                    vendorSearchUrls.append(VendorSearchListing(record[0], record[1], record[2], record[3]))
                        
        return vendorSearchUrls
    # END - HELPER METHODS #
            
