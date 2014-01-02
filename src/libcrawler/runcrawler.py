import sys
import psycopg2
import crawlerfactory
from util import dbconnector

if len(sys.argv) != 2:
    print "Usage: python runcrawler <vendor_id>"
    print "Exiting.."
    sys.exit(0)

vendor_id   = int(sys.argv[1])

conn        = psycopg2.connect(dbconnector.DbConnector.get_db_str("util"))
crawlerFact = crawlerfactory.CrawlerFactory(conn)
crawler     = crawlerFact.get_crawler(vendor_id)

if crawler is None:
    print "No crawler found for vendor_id: " + str(vendor_id)
else:
    crawler.run()
