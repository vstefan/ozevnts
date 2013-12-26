import moshtixcrawler
import oztixcrawler

class CrawlerFactory(object):
    """ 
        Stores a mapping of vendor_id : crawler and provides a
        method for other classes to get the correct crawler. 
    """
    def __init__(self, dbCon):
            self.crawlerMap = {}
            moshtixCrawler  = moshtixcrawler.MoshtixCrawler(dbCon)
            oztixCrawler    = oztixcrawler.OztixCrawler(dbCon)
            
            self.crawlerMap[moshtixCrawler.vendorId] = moshtixCrawler
            self.crawlerMap[oztixCrawler.vendorId]   = oztixCrawler

    def getCrawler(self, vendorId):
        """ Given a vendorId, returns an appropriate crawler. """
        return self.crawlerMap.get(vendorId)
