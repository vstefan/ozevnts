import abc
import time
import requests
import codecs
import gc
import logging

#enable for testing memory usage
#from guppy import hpy


class VendorSearchListing:
    """ Vendor data for a event/ticket search listing. """

    def __init__(self, vendor_id, event_type_id, search_url, paginated_ind):
        self.vendor_id     = vendor_id
        self.event_type_id = event_type_id
        self.search_url    = search_url

        if paginated_ind is not None and paginated_ind == "Y":
            self.paginated_ind = True
        else:
            self.paginated_ind = False

    def __repr__(self):
        return "vendor_id: " + str(self.vendor_id) + ", event_type_id: " + str(
            self.event_type_id) + ", search_url: " + self.search_url + ", paginated_ind: " + str(self.paginated_ind)


class EventInfo:
    """ Event info extracted from search results & event pages or loaded from db. """

    def __init__(self, vendor_id, event_type_id, event_name, url):
        self.vendor_id        = vendor_id
        self.event_type_id    = event_type_id
        self.event_name       = event_name
        self.url              = url
        self.venue_name       = None
        self.venue_state      = None
        self.event_datetime   = None
        self.invalid          = None
        self.vendor_event_id  = None
        self.ticket_list      = []

    def invalid_db_val(self):
        if self.invalid:
            return "Y"
        else:
            return None

    def __repr__(self):
        return "vendor_id: " + str(self.vendor_id) + ", event_type_id: " + str(
            self.event_type_id) + ", eventName: " + self.event_name + ", url: " + self.url + ", venueName: " + \
            self.venue_name + ", venueState: " + self.venue_state + ", eventDateTime: " + \
            str(self.event_datetime) + ", invalid + " + str(self.invalid) + ", vendorEventId: " + \
            str(self.vendor_event_id)

    def create_event(self, db_con):
        with db_con.cursor() as cur1:
            cur1.callproc("ozevnts.create_event",
                          [self.vendor_id, self.event_type_id, self.event_name, self.venue_state, self.event_datetime,
                           self.invalid_db_val(), self.url])

            self.vendor_event_id = int(cur1.fetchone()[0])

    def create_tickets(self, db_con):
        """ Record a list of tickets for this event. """
        if self.vendor_event_id is None:
            error_msg = "Invalid VendorEventId; unable to create_tickets for eventName: " + self.event_name
            logging.error(error_msg)
            raise Exception(error_msg)
        elif not self.invalid:
            for ticketInfo in self.ticket_list:
                ticketInfo.create(db_con, self.vendor_event_id)

    def invalidate_event(self, db_con):
        """ Updated an event as now being invalid. """
        if self.invalid:
            with db_con.cursor() as cur1:
                cur1.callproc("ozevnts.invalidate_event", [self.vendor_event_id])


class TicketInfo:
    """ Ticket info extracted from event page or loaded from db. """

    def __init__(self, ticket_num, ticket_type, ticket_price, booking_fee, sold_out):
        self.ticket_num   = ticket_num
        self.ticket_type  = ticket_type
        self.ticket_price = ticket_price
        self.booking_fee  = booking_fee
        self.sold_out     = sold_out

    def sold_out_db_val(self):
        if self.sold_out:
            return "Y"
        else:
            return None

    def has_been_updated(self, new_ticket):
        """ Returns true if any details retrieved in a refresh from vendor have changed. """
        return self.ticket_type != new_ticket.ticket_type or self.ticket_price != new_ticket.ticket_price or \
            self.booking_fee != new_ticket.booking_fee or self.sold_out != new_ticket.sold_out

    def create(self, db_con, vendor_event_id):
        with db_con.cursor() as cur1:
            cur1.callproc("ozevnts.create_ticket",
                          [vendor_event_id, self.ticket_num, self.ticket_type, self.ticket_price, self.booking_fee,
                           self.sold_out_db_val()])

    def update(self, db_con, vendor_event_id):
        with db_con.cursor() as cur1:
            cur1.callproc("ozevnts.update_ticket",
                          [vendor_event_id, self.ticket_num, self.ticket_type, self.ticket_price, self.booking_fee,
                           self.sold_out_db_val()])

    def __repr__(self):
        return "ticketNum: " + str(self.ticket_num) + ", ticket_type: " + self.ticket_type + ", ticket_price: " + str(
            self.ticket_price) + ", booking_fee: " + str(self.booking_fee) + ", sold_out: " + str(self.sold_out)


# START - MISC UTILITY FUNCTIONS # 
def fetch_url(url):
    fetched = False
    output  = None

    while not fetched:
        try:
            logging.info("Opening url: " + url)
            output  = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
            fetched = True
        except requests.Timeout, e:
            #timeout, wait 30 seconds and try again
            logging.debug("Received timeout, retrying in 30 seconds...")
            time.sleep(30)

    # for debugging raw response data
    out_file = codecs.open("output.html", "w", "utf-8")
    out_file.write(output.text)
    out_file.close()

    return output
# END - MISC UTILITY FUNCTIONS #


class ICrawler(object):
    """ Abstract class which all site-specific crawlers must implement. """
    __metaclass__ = abc.ABCMeta

    def __init__(self, db_con):
        self.db_con = db_con

    # START - ABSTRACT METHODS REQUIRING VENDOR-SPECIFIC IMPLEMENTATION #
    @abc.abstractmethod
    def extract_new_events(self, event_type_id, known_urls, search_results):
        """ Parses search results to extract basic event info for unknown events. """
        return

    @abc.abstractmethod
    def extract_ticket_info(self, event_info, event_page):
        """ Parses event page to extract further event and ticket info. """
        return

    @abc.abstractmethod
    def extract_subsequent_urls(self, search_results):
        """ Handles pagination from vendor-specific search results. """
        return

    @abc.abstractmethod
    def fetch_event_url(self, url):
        """ 
            Some vendors do cookie checks with mess redirects which
            require unique handling in vendor-specific implementations.
        """
        return fetch_url(url)

    @abc.abstractmethod
    def extract_event_and_ticket_info(self, event_type_id, known_urls, search_results):
        """ Extracts event & ticket info from retrieved search results. """
        extracted_event_info_list = self.extract_new_events(event_type_id, known_urls, search_results)

        while extracted_event_info_list:
            extracted_event_info = extracted_event_info_list.pop()
            event_page           = self.fetch_event_url(extracted_event_info.url).text
            self.extract_ticket_info(extracted_event_info, event_page)
            extracted_event_info.create_event(self.db_con)
            extracted_event_info.create_tickets(self.db_con)

            self.db_con.commit()
            event_page           = None
            extracted_event_info = None
            gc.collect()

    @abc.abstractmethod
    def process_search_url(self, event_type_id, search_url, paginated_ind):
        """ Processes a search url to extract all event/ticket info. """
        known_urls     = self.get_known_urls()
        search_results = fetch_url(search_url).text

        self.extract_event_and_ticket_info(event_type_id, known_urls, search_results)

        if paginated_ind:
            for subsequent_url in self.extract_subsequent_urls(search_results):
                known_urls     = self.get_known_urls()
                search_results = fetch_url(subsequent_url).text
                self.extract_event_and_ticket_info(event_type_id, known_urls, search_results)

    @abc.abstractmethod
    def run(self):
        """ Starts crawling. """
        while True:
            vendor_search_urls = self.get_vendor_search_urls()

            for vendor_search_url in vendor_search_urls:
                self.process_search_url(vendor_search_url.event_type_id, vendor_search_url.search_url,
                                        vendor_search_url.paginated_ind)

            vendor_search_urls = None
            gc.collect()
            #enable for testing memory usage
            #h = hpy()
            #print h.heap()
            logging.info("Finished crawl cycle, sleeping..")
            time.sleep(60 * 60 * 4)
    # END - ABSTRACT METHODS REQUIRING VENDOR-SPECIFIC IMPLEMENTATION #

    # START - ABSTRACT PROPERTIES REQUIRING VENDOR-SPECIFIC VALUES #
    @abc.abstractproperty
    def vendor_id(self):
        """ Vendor specific id. """
        return

    @abc.abstractproperty
    def vendor_url(self):
        """ Vendor specific url. """
        return
    # END - ABSTRACT PROPERTIES REQUIRING VENDOR-SPECIFIC VALUES #

    # START - HELPER METHODS #
    def load_tickets_for_event(self, event_info):
        """ Given a EventInfo with a valid url, loads tickets for that event. """
        event_page = self.fetch_event_url(event_info.url).text
        self.extract_ticket_info(event_info, event_page)

    def get_known_urls(self):
        """ Given a database connection, fetches known urls. """
        known_urls = set()

        with self.db_con.cursor() as cur1:
            cur1.callproc("ozevnts.get_known_urls", ["known_urls_curname", self.vendor_id])

            with self.db_con.cursor("known_urls_curname") as cur2:
                for record in cur2:
                    known_urls.add(record[0])

        return known_urls

    def get_vendor_search_urls(self):
        """ Given a database connection, fetches vendor search urls. """
        vendor_search_urls = []

        with self.db_con.cursor() as cur1:
            cur1.callproc("ozevnts.get_search_urls", ["search_urls_curname", self.vendor_id])

            with self.db_con.cursor("search_urls_curname") as cur2:
                for record in cur2:
                    #print record
                    vendor_search_urls.append(VendorSearchListing(record[0], record[1], record[2], record[3]))

        return vendor_search_urls
    # END - HELPER METHODS #
