import decimal
import logging
from bs4 import BeautifulSoup
from datetime import datetime

import libcrawler


class MoshtixCrawler(libcrawler.ICrawler):
    def create_datetime_from_moshtix_str(self, datetime_str, month_format_mask):
        """
            MoshTix uses multiple formats (short & long) for month display.
        """
        datetime_str_tokens = datetime_str.split(",")
        day_month_tokens    = datetime_str_tokens[1].lstrip().split(" ")

        filtered_datetime_str = datetime_str_tokens[0] + " " + day_month_tokens[1][0:len(day_month_tokens[1]) - 2] + \
            " " + day_month_tokens[2] + " " + datetime_str_tokens[2].lstrip()

        return datetime.strptime(filtered_datetime_str, "%I:%M%p %d " + month_format_mask + " %Y")

    def create_datetime_from_moshtix_event_date_str(self, datetime_str):
        """ 
            extracts starting datetime from formats like "5:00pm, Fri 4th October, 2013"
            and ""9:00pm, Fri 20th December, 2013 - 4:00am, Sat 28th December, 2013" 
        """
        sep_index = datetime_str.find("-")
        if sep_index != -1:
            return self.create_datetime_from_moshtix_str(datetime_str[0:sep_index - 1], "%B")
        else:
            return self.create_datetime_from_moshtix_str(datetime_str, "%B")

    def extract_ticket_info(self, event_info, event_page):
        ticket_type  = None
        ticket_price = None
        booking_fee  = None
        sold_out     = False

        logging.info("Now processing: " + event_info.url)

        # find <div> with id = "event-summary-block"
        soup = BeautifulSoup(event_page)
        event_summary_div_tag = soup.find("div", id="event-summary-block")

        if event_summary_div_tag is not None:
            event_info.event_datetime = self.create_datetime_from_moshtix_event_date_str(
                event_summary_div_tag["data-event-date"])
            venue_tokens = event_summary_div_tag["data-event-venue"].split(",")

            # format examples: "Enigma Bar, SA"
            #                : "Candy's Apartment, Kings Cross, NSW"
            #                : "Duke of Wellington, 146 Flinders St, Melbourne, VIC"
            if len(venue_tokens) >= 2:
                event_info.venue_name = venue_tokens[0]
                event_info.venue_state = venue_tokens[len(venue_tokens) - 1].lstrip()

        if event_info.event_datetime is None:
            error_msg = "Failed to parse event date/time from: " + event_info.url
            logging.error(error_msg)
            raise Exception(error_msg)

        if event_info.venue_state is None:
            error_msg = "Failed to parse venue state from: " + event_info.url
            logging.error(error_msg)
            raise Exception(error_msg)

        # find <table> with id = "event-tickettypetable"
        ticket_table_tag = soup.find("table", id="event-tickettypetable")

        if ticket_table_tag is not None:
            ticket_table_body_tag = ticket_table_tag.find("tbody")

            if ticket_table_body_tag is not None:
                ticket_table_row_tags = ticket_table_body_tag.find_all("tr")

                # 1 row for each ticket type
                if ticket_table_row_tags is not None and len(ticket_table_row_tags) > 0:
                    ticket_num = 1
                    for ticket_table_row_tag in ticket_table_row_tags:
                        ticket_table_row_tag_col_tags = ticket_table_row_tag.find_all("td")

                        # each ticket type should have 6 columns (ticket type, sale date, ticket price,
                        # booking fee, total price, amount of tickets or sold out)
                        if ticket_table_row_tag_col_tags is not None:
                            if len(ticket_table_row_tag_col_tags) == 7:
                                ticket_type  = ticket_table_row_tag_col_tags[0].contents[2].string.strip()
                                ticket_price = decimal.Decimal(
                                    ticket_table_row_tag_col_tags[2].string[1:].replace(",", ""))
                                booking_fee  = decimal.Decimal(ticket_table_row_tag_col_tags[4].string[1:].replace(
                                    ",", ""))

                                if len(ticket_table_row_tag_col_tags[6].contents) == 1:
                                    ticket_selling_str = ticket_table_row_tag_col_tags[6].string.strip()

                                    if ticket_selling_str.lower() == "allocation exhausted":
                                        sold_out = True

                                event_info.ticket_list.append(
                                    libcrawler.TicketInfo(ticket_num, ticket_type, ticket_price, booking_fee, sold_out))
                                ticket_num += 1
                            else:
                                error_msg = "Unknown length of ticket_table_row_tag_col_tags = " + str(
                                    len(ticket_table_row_tag_col_tags))
                                logging.error(error_msg)
                                raise Exception(error_msg)
        else:
            event_info.invalid = True

        # if this url had no extracted tickets, add a dummy entry
        # so this url will be saved and ignored in the future
        if not event_info.ticket_list:
            event_info.invalid = True

    def extract_subsequent_urls(self, search_results):
        subsequent_urls     = []
        search_results_soup = BeautifulSoup(search_results)
        pagination_tag      = search_results_soup.find("section", class_="pagination")

        if pagination_tag is not None:
            ahref_tags = pagination_tag.find_all("a")

            if ahref_tags is not None and len(ahref_tags) > 0:
                for ahref_tag in ahref_tags:
                    if len(ahref_tag["href"]) > 0 and "class" not in ahref_tag:
                        subsequent_urls.append(self.vendor_url + ahref_tag["href"])

        return subsequent_urls

    def extract_new_events(self, event_type_id, known_urls, search_results):
        event_list             = []
        search_results_soup    = BeautifulSoup(search_results)
        search_result_div_tags = search_results_soup.find_all("div", {"class": "searchresult_content"})

        if search_result_div_tags is not None and len(search_result_div_tags) > 0:
            for search_result_div_tag in search_result_div_tags:
                url        = search_result_div_tag.contents[1]["href"]
                event_name = search_result_div_tag.contents[3].contents[0].string.replace("&#39;", "'")

                if url is not None and event_name is not None and url not in known_urls:
                    event_list.append(libcrawler.EventInfo(self.vendor_id, event_type_id, event_name, url))
        else:
            error_msg = "No searchresult_content div tags found."
            logging.error(error_msg)
            raise Exception(error_msg)

        return event_list

    def fetch_event_url(self, url):
        return super(MoshtixCrawler, self).fetch_event_url(url)

    def extract_event_and_ticket_info(self, event_type_id, known_urls, search_results):
        super(MoshtixCrawler, self).extract_event_and_ticket_info(event_type_id, known_urls, search_results)

    def process_search_url(self, event_type_id, search_url, paginated_ind):
        super(MoshtixCrawler, self).process_search_url(event_type_id, search_url, paginated_ind)

    def run(self):
        super(MoshtixCrawler, self).run()

    @property
    def vendor_id(self):
        return 1

    @property
    def vendor_url(self):
        return "http://www.moshtix.com.au"


# for re-testing specific problematic urls
#moshtixCrawler.process_search_url(3, " http://moshtix.com.au/v2/search?CategoryList=3%2C&Page=5", False)
