import json
import decimal
import logging
import re
from bs4 import BeautifulSoup
from datetime import datetime

import libcrawler

seat_selection_tag_re = re.compile("^event_seat_selection")
ticket_type_tag_re    = re.compile("^classic_ticket_type")
au_re                 = re.compile("^AU")
booking_re            = re.compile("A Handling Fee from")
deleted_event_re      = re.compile("this event no longer exists")
tickets_not_yet_re    = re.compile("Tickets are not currently available")


class TicketmasterCrawler(libcrawler.ICrawler):

    def create_datetime_from_tm_event_date_str(self, datetime_str):
        # eg: "2014-01-12T12:00:00+11:00"
        sep_index = datetime_str.find("+")
        if sep_index != -1:
            datetime_str = datetime_str[0:sep_index]

        return datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%S")

    def extract_tickets_method1(self, booking_fee, event_info, soup):
        ticket_type   = None
        ticket_price  = None
        sold_out      = False
        found_tickets = False

        logging.info("attempting to extract ticketmaster tickets via method #1.")

        # find <div> with id that starts with "event_seat_selection" which holds tickets
        seat_selection_tag = soup.find("div", id=seat_selection_tag_re)

        if seat_selection_tag is not None:
            # find all child <div>s that contain id which starts with "classic_ticket_type"
            ticket_type_tags = seat_selection_tag.find_all("div", id=ticket_type_tag_re)

            if ticket_type_tags is not None:
                ticket_num = 1

                for ticket_type_tag in ticket_type_tags:
                    ticket_type = ticket_type_tag.contents[1].contents[0].string.replace("&#39;", "'")
                    span_tags   = ticket_type_tag.find_all("span", class_="widget-wrapper")

                    if ticket_type.lower() != unicode("special offers and promotions", "utf-8"):
                        if span_tags is not None and len(span_tags) >= 2:
                            # second <span> has the price info
                            ticket_price_list_tag \
                                = span_tags[1].find("ul", class_="widget-dropdown-list module-js-ignore")

                            if ticket_price_list_tag is not None:
                                ticket_price_str = ticket_price_list_tag.find(text=au_re)
                                if ticket_price_str is not None:
                                    ticket_price = decimal.Decimal(ticket_price_str[4:].rstrip().replace(",", ""))

                                    event_info.ticket_list.append(
                                        libcrawler.TicketInfo(ticket_num, ticket_type, ticket_price, booking_fee, sold_out))
                                    ticket_num += 1
                                    found_tickets = True
                                else:
                                    error_msg = "No ticket price string (^AU) found."
                                    logging.error(error_msg)
                                    #raise Exception(error_msg)
                            else:
                                error_msg = "No <ul> with class='widget-dropdown-list module-js-ignore' found."
                                logging.error(error_msg)
                                #raise Exception(error_msg)
                        else:
                            error_msg = "No <span> with class=widget_wrapper for ticket price found."
                            logging.error(error_msg)
                            #raise Exception(error_msg)

        return found_tickets

    def extract_tickets_method2(self, booking_fee, event_info, soup):
        ticket_type   = None
        ticket_price  = None
        sold_out      = False
        found_tickets = False

        logging.info("attempting to extract ticketmaster tickets via method #2.")

        price_range_tag = soup.find("div", id="price-range-popup")

        if price_range_tag is not None:
            event_info_max_tag = price_range_tag.find("div", class_="eventInfoMax")

            if event_info_max_tag is not None:
                ticket_num = 1

                ticket_type_tags  = event_info_max_tag.contents[1].find_all("div", class_="")
                ticket_price_tags = event_info_max_tag.contents[1].find_all("span", itemprop="price")

                num_ticket_type_tags  = len(ticket_type_tags)
                num_ticket_price_tags = len(ticket_price_tags)

                if num_ticket_type_tags > 0 and num_ticket_price_tags > 0 and (
                        num_ticket_type_tags == num_ticket_price_tags):

                    for idx in range(num_ticket_type_tags):
                        ticket_type  = ticket_type_tags[idx].string.strip().replace("&#39;", "'")

                        if ticket_type.lower() != unicode("special offers and promotions", "utf-8"):
                            ticket_price = decimal.Decimal(ticket_price_tags[idx].string.strip().replace(",", ""))

                            event_info.ticket_list.append(
                                libcrawler.TicketInfo(ticket_num, ticket_type, ticket_price, booking_fee, sold_out))
                            ticket_num += 1
                            found_tickets = True
                else:
                    logging.error("Ticket type & price length mismatch, " +
                                  "num_ticket_type_tags = " + str(num_ticket_type_tags) +
                                  ", num_ticket_price_tags = " + str(num_ticket_price_tags))
            else:
                logging.error("No <div> eventInfoMax tag found.")
        else:
            logging.error("No <div> price-range-popup tag found.")

        return found_tickets

    def extract_ticket_info(self, event_info, event_page):
        logging.info("Now processing: " + event_info.url)

        booking_fee = decimal.Decimal("0")
        soup        = BeautifulSoup(event_page)

        # find booking fee
        booking_fee_str = soup.find(text=booking_re)
        if booking_fee_str is not None:
            dollar_index = booking_fee_str.find("$")
            per_index    = booking_fee_str.find("per")
            if dollar_index != -1 and per_index != -1:
                booking_fee = decimal.Decimal(booking_fee_str[dollar_index+1:per_index].rstrip())
            else:
                error_msg = "dollar_index: " + str(dollar_index) + ", per_index: " + str(per_index)
                logging.error(error_msg)
                raise Exception(error_msg)

        if not self.extract_tickets_method1(booking_fee, event_info, soup):
            if soup.find(text=deleted_event_re) is not None:
                event_info.invalid = True
            elif not self.extract_tickets_method2(booking_fee, event_info, soup):

                if soup.find(text=tickets_not_yet_re) is not None:
                    error_msg = "No event_seat_selection tag, price-range-popup tag, event deleted text," + \
                                " or tickets not available text found."
                    logging.error(error_msg)
                    raise Exception(error_msg)

        # if this url had no extracted tickets, add a dummy entry
        # so this url will be saved and ignored in the future
        # don't do this for ticket master as they don't display multi-state general events
        # in their search results, and sometimes turn off ticket selling for a short period,
        # so don't want to work events as invalid due to their technical problems.
        #if not event_info.ticket_list:
        #    event_info.invalid = True

    # ticketmaster fetches all events in one json response, no pagination required.
    def extract_subsequent_urls(self, search_results):
        return

    def extract_new_events(self, event_type_id, known_urls, search_results):
        event_list          = []
        search_results_json = json.loads(search_results)

        if int(search_results_json["response"]["numFound"]) > 0:
            for item in search_results_json["response"]["docs"]:
                url = self.vendor_url + "/" + item["EventSEOName"] + "/event/" + item["EventId"]

                if url not in known_urls:
                    event_info = libcrawler.EventInfo(
                        self.vendor_id, event_type_id, item["EventName"].replace("&#39;", "'"), url)
                    event_info.venue_state    = item["VenueState"]
                    event_info.event_datetime = self.create_datetime_from_tm_event_date_str(
                        item["PostProcessedData"]["LocalEventDate"])

                    event_list.append(event_info)

        return event_list

    def fetch_event_url(self, url):
        return super(TicketmasterCrawler, self).fetch_event_url(url)

    def extract_event_and_ticket_info(self, event_type_id, known_urls, search_results):
        super(TicketmasterCrawler, self).extract_event_and_ticket_info(event_type_id, known_urls, search_results)

    def process_search_url(self, event_type_id, search_url, paginated_ind):
        super(TicketmasterCrawler, self).process_search_url(event_type_id, search_url, paginated_ind)

    def run(self):
        super(TicketmasterCrawler, self).run()

    @property
    def vendor_id(self):
        return 3

    @property
    def vendor_url(self):
        return "http://www.ticketmaster.com.au"

