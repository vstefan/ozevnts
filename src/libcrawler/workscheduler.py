import logging
import datetime
import time
import gc
import psycopg2

from util import dbconnector
import crawlerfactory
import refresher


def run_crawler(crawler_id):
    with psycopg2.connect(dbconnector.DbConnector.get_db_str("util")) as conn:
        crawlerFact = crawlerfactory.CrawlerFactory(conn)
        crawler     = crawlerFact.get_crawler(crawler_id)

        if crawler is None:
            error_msg = "No crawler found for crawler_id: " + str(crawler_id)
            logging.error(error_msg)
            raise Exception(error_msg)
        else:
            crawler.run()


def run_refresher(dummy):
    refresher.run()


class ExecItem:
    def __init__(self, last_exec_fin_time, sec_between_execs, func_ref):
        self.last_exec_fin_time = last_exec_fin_time
        self.sec_between_execs  = sec_between_execs
        self.func_ref           = func_ref


# work scheduler execution starts here
# ensures only 1 crawler/refresher running at once
# to minimise memory usage
exec_ids = [0,  # refresher,
            1,  # crawler: moshtix,
            2,  # crawler: oztix,
            3]  # crawler: ticketmaster

# maps ids to execute against last exec finish time, time (sec) between execs, and reference run() function
exec_time_map = {0: ExecItem(None, 60*20,   run_refresher),
                 1: ExecItem(None, 60*60*4, run_crawler),
                 2: ExecItem(None, 60*60*4, run_crawler),
                 3: ExecItem(None, 60*60*4, run_crawler)}

logging.basicConfig(
    filename="logs/WorkScheduler.log", filemode="w",
    format="%(asctime)s %(module)s:%(levelname)s: %(message)s", level=logging.NOTSET)

while True:
    min_next_exec_time = None

    for exec_id in exec_ids:
        exec_item = exec_time_map.get(exec_id)
        time_now  = datetime.datetime.now()

        if exec_item.last_exec_fin_time is None or (
            time_now - datetime.timedelta(
                seconds=exec_item.sec_between_execs) >= exec_item.last_exec_fin_time):

            exec_item.func_ref(exec_id)

            time_now = datetime.datetime.now()
            exec_item.last_exec_fin_time = time_now

            gc.collect()
            next_exec_time = time_now + datetime.timedelta(seconds=exec_item.sec_between_execs)

            if min_next_exec_time is None or next_exec_time < min_next_exec_time:
                min_next_exec_time = next_exec_time

    # if next job to execute is in the future, sleep until that time
    time_now = datetime.datetime.now()

    if min_next_exec_time > time_now:
        time_delta = min_next_exec_time - time_now
        sleep_sec  = time_delta.total_seconds()+1

        logging.info("Sleeping " + str(sleep_sec) + " seconds until next job at: " + str(min_next_exec_time))
        time.sleep(sleep_sec)
