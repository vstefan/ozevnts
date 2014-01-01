
class DbConnector(object):
    db_str = None

    @staticmethod
    def get_db_str(dir_path):
        if DbConnector.db_str is None:
            with open(dir_path + "/dbstr.conf") as db_str_file:
                DbConnector.db_str = db_str_file.readline()

        return DbConnector.db_str
