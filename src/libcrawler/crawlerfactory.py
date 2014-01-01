import moshtixcrawler
import oztixcrawler


class CrawlerFactory(object):
    """ 
        Stores a mapping of vendor_id : crawler and provides a
        method for other classes to get the correct crawler. 
    """

    def __init__(self, db_con):
        self.crawler_map = {}
        moshtix_crawler  = moshtixcrawler.MoshtixCrawler(db_con)
        oztix_crawler    = oztixcrawler.OztixCrawler(db_con)

        self.crawler_map[moshtix_crawler.vendor_id] = moshtix_crawler
        self.crawler_map[oztix_crawler.vendor_id]   = oztix_crawler

    def get_crawler(self, vendor_id):
        """ Given a vendorId, returns an appropriate crawler. """
        return self.crawler_map.get(vendor_id)
