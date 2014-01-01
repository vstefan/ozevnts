import decimal
import requests
import time
from bs4 import BeautifulSoup
from datetime import datetime

import libcrawler


class OztixCrawler(libcrawler.ICrawler):
    def create_datetime_from_oztix_event_date_str(self, datetime_str):
        """ 
            extracts starting datetime from formats like "Tuesday 31 December 2013  (opening 8:00pm)"
            and "Saturday 04 January 2014 (opening 1pm)"
            and "Tuesday 31 December 2013  to Friday 03 January 2014"
            and "Wednesday 01 January 2014  (opening Midday-10.30pm)"
            and "Saturday 28 December 2013   4.00 PM"
            and "Tuesday 31 December 2013   9:00 PM"
            and "Tuesday 07 January 2014 12:30:00"
        """
        datetime_str = datetime_str.replace("(opening", "")
        datetime_str = datetime_str.replace(")", "")
        datetime_str = datetime_str.replace("Midday", "12:00pm")
        datetime_str = datetime_str.replace(".", ":")

        # if there is an end date, delete it
        sep_index = datetime_str.find("to")
        if sep_index != -1:
            return datetime.strptime(datetime_str[0:sep_index].rstrip(), "%A %d %B %Y")
        else:
            # now check for second type of end date
            sep_index = datetime_str.find("-")
            if sep_index != -1:
                datetime_str = datetime_str[0:sep_index]

            # and a third unicode type
            sep_index = datetime_str.find(u"\u2014")
            if sep_index != -1:
                datetime_str = datetime_str[0:sep_index]

            # now looks like: "Tuesday 31 December 2013  8:00pm"
            #              or "Tuesday 31 December 2013   9:00 PM"
            #              or "Tuesday 31 December 2013  8pm"
            datetime_str_tokens = datetime_str.split()
            datetime_str = datetime_str_tokens[0].strip() + " " + datetime_str_tokens[1].strip() + " " + \
                datetime_str_tokens[2].strip() + " " + datetime_str_tokens[3].strip() + " " + \
                datetime_str_tokens[4].strip()

            if len(datetime_str_tokens) == 6:
                datetime_str += datetime_str_tokens[5]

            # now looks like: "Tuesday 31 December 2013 8:00pm"
            #              or "Tuesday 31 December 2013 9:00PM"
            #              or "Tuesday 31 December 2013 8pm"
            #              or "Tuesday 07 January 2014 12:30:00"
            sep_count = datetime_str.count(":")
            if sep_count == 1:
                return datetime.strptime(datetime_str, "%A %d %B %Y %I:%M%p")
            elif sep_count == 2:
                return datetime.strptime(datetime_str, "%A %d %B %Y %H:%M:%S")
            else:
                return datetime.strptime(datetime_str, "%A %d %B %Y %I%p")

    def extract_ticket_info(self, event_info, event_page):
        ticket_type  = None
        ticket_price = None
        booking_fee  = None
        sold_out     = False

        print "Now processing: " + event_info.url

        # find <div> with id = "venueInfo"
        soup = BeautifulSoup(event_page.text)
        event_summary_div_tag = soup.find("div", class_="venueInfo")

        if event_summary_div_tag:
            # date/time always before this next tag, but sometimes has other tags
            # in front of it, so most reliable way of getting to it is working backwards
            div_venue_tag = event_summary_div_tag.find(
                "div", id="ctl00_ContentPlaceHolder1_WucShowsMain1_WucEventsDetail1_pnl_venue")

            if div_venue_tag is not None and div_venue_tag.previous_sibling is not None and (
                    div_venue_tag.previous_sibling.previous_sibling is not None):
                event_info.event_datetime = self.create_datetime_from_oztix_event_date_str(
                    div_venue_tag.previous_sibling.previous_sibling.string.strip())

        if event_info.event_datetime is None:
            event_info.invalid = True
            return

        # find <table> with tsClass = "ReserveTable"
        # note: find won't work with "tsClass" specified, only works with "tsclass"
        #       even though in the raw source it shows "tsClass", gets converted
        #       to "tsclass" somewhere in the parsing (can check via print tag)
        ticket_table_tag = soup.find("table", attrs={"tsclass": "ReserveTable"})

        if ticket_table_tag is not None:
            ticket_table_row_tags = ticket_table_tag.find_all("tr")

            # 1 row for each ticket type
            if ticket_table_row_tags is not None and len(ticket_table_row_tags) > 0:
                ticket_num = 1
                for ticket_table_row_tag in ticket_table_row_tags:
                    ticket_table_row_tag_col_tags = ticket_table_row_tag.find_all("td")

                    # only care about first two columns: {ticket_type, total_price}
                    # oztix doesn't display booking fee, only all-inclusive price
                    if ticket_table_row_tag_col_tags is not None:
                        if len(ticket_table_row_tag_col_tags) >= 2 and ticket_table_row_tag_col_tags[0].contents[
                                0].string is not None and ticket_table_row_tag_col_tags[1].string is not None:
                            ticket_type = ticket_table_row_tag_col_tags[0].contents[0].string.strip()
                            ticket_price = decimal.Decimal(ticket_table_row_tag_col_tags[1].string[4:])
                            booking_fee = decimal.Decimal(0)

                            if len(ticket_table_row_tag_col_tags) >= 3 and ticket_table_row_tag_col_tags[2].contents[
                                0].string is not None and ticket_table_row_tag_col_tags[2].contents[
                                    0].string.lower() == "sold out":
                                sold_out = True
                            else:
                                sold_out = False

                            event_info.ticket_list.append(
                                libcrawler.TicketInfo(ticket_num, ticket_type, ticket_price, booking_fee, sold_out))
                            ticket_num += 1
                            # dont throw an exception here as oztix can place promo crap before and after
                            # each ticket category & price
                            #else:
                            #    raise Exception("Unknown length of ticket_table_row_tag_col_tags = " + \
                            #       str(len(ticket_table_row_tag_col_tags)))
        else:
            event_info.invalid = True

        # if this url had no extracted tickets, add a dummy entry
        # so this url will be saved and ignored in the future
        if not event_info.ticket_list:
            event_info.invalid = True

    # oztix shows everything on one page for each category, no pagination required.
    def extract_subsequent_urls(self, search_results_soup):
        return

    def extract_new_events(self, event_type_id, known_urls, search_results_soup):
        event_list = []

        state_header_div_tags = search_results_soup.find_all("div", class_="state_header")

        if state_header_div_tags is not None and len(state_header_div_tags) > 0:
            for state_header_div_tag in state_header_div_tags:
                venue_state = state_header_div_tag.a["name"]

                if venue_state is not None and len(venue_state) > 0:
                    next_state_header_tag_found = False
                    next_div_sibling = state_header_div_tag.find_next_sibling("div")

                    while not next_state_header_tag_found:
                        if next_div_sibling is not None and next_div_sibling.get("class") is None and (
                                next_div_sibling.get("id") is not None and next_div_sibling["id"] == "gigtable"):
                            search_result_div_tags = next_div_sibling.find_all("div", class_="gigname")

                            if search_result_div_tags is not None and len(search_result_div_tags) > 0:
                                for search_result_div_tag in search_result_div_tags:
                                    url        = search_result_div_tag.contents[0]["href"]
                                    event_name = search_result_div_tag.contents[0].string

                                    if url is None or event_name is None:
                                        raise Exception("Failed to read url or EventName from gigname search results.")

                                    next_div_sibling = next_div_sibling.find_next_sibling("div")

                                    if url is not None and event_name is not None and url not in known_urls:
                                        event_info = libcrawler.EventInfo(self.vendor_id, event_type_id, event_name, url)
                                        event_info.venue_state = venue_state

                                        event_list.append(event_info)
                            else:
                                raise Exception("No gigname tags found.")
                        elif next_div_sibling is None or next_div_sibling.get("class") is not None and (
                                next_div_sibling["class"][0] == "state_header"):
                            next_state_header_tag_found = True
                        else:
                            raise Exception(
                                "Unknown div tag in gigtable/state_header siblings found: " + str(next_div_sibling))
                else:
                    raise Exception("Venue state not found in state_header tag.")
        else:
            raise Exception("No state header tags found.")

        return event_list

    def fetch_event_url(self, url):
        fetched = False
        output  = False

        while not fetched:
            try:
                r1      = requests.get(url, allow_redirects=False, headers={"User-Agent": "Mozilla/5.0"})
                output  = requests.get(url, cookies=r1.cookies,    headers={"User-Agent": "Mozilla/5.0"})
                fetched = True
            except requests.Timeout, e:
                #timeout, wait 30 seconds and try again
                print "Received timeout, retrying in 30 seconds..."
                time.sleep(30)

        return output

    def extract_event_and_ticket_info(self, event_type_id, known_urls, search_results_soup):
        super(OztixCrawler, self).extract_event_and_ticket_info(event_type_id, known_urls, search_results_soup)

    def process_search_url(self, event_type_id, search_url, paginated_ind):
        super(OztixCrawler, self).process_search_url(event_type_id, search_url, paginated_ind)

    def run(self):
        super(OztixCrawler, self).run()

    @property
    def vendor_id(self):
        return 2

    @property
    def vendor_url(self):
        return "http://oztix.com.au"


# for re-testing specific problematic urls
#oztixCrawler.process_search_url(1, "http://www.oztix.com.au/OzTix/OzTixEvents/OzTixFestivals/tabid/1100/Default.aspx", False)
