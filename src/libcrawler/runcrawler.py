import sys
import psycopg2
import crawlerfactory

if len(sys.argv) != 2:
    print "Usage: python runcrawler <vendor_id>"
    print "Exiting.."
    sys.exit(0)

vendorId = int(sys.argv[1])
    
conn = psycopg2.connect(host="192.168.2.105", database="ozevntsdb", user="ozevntsapp", password="test")
crawlerFact = crawlerfactory.CrawlerFactory(conn)
crawler     = crawlerFact.getCrawler(vendorId)

if crawler is None:
    print "No crawler found for vendor_id: " + str(vendorId)
else:    
    crawler.run()
