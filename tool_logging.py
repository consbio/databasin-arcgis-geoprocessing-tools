import time,logging,os
import settings


class ToolLogFileStream:
    def __init__(self, filename):
        self.filename = filename
        directory=os.path.split(filename)[0]
        if not os.path.exists(directory):
            os.makedirs(directory)

    def write(self, data):
        f = open(self.filename, 'a')
        f.write(data)
        f.close()

    def flush(self):
        pass


class ToolLogger(logging.Logger):
    """
    Extends builtin python logger to provide logging capabilities for geoprocessing tools.  Writes to the log file
    specified in settings.py (LOG_FILENAME).  Will roll the logfile each day.

    .. note:: does not prune old log files.

    """

    def __init__(self, name):
        logging.Logger.__init__(self, name)
        self.handler = logging.StreamHandler(ToolLogFileStream(settings.LOG_FILENAME))
        self.handler.setLevel(logging.DEBUG)
        format = "%(asctime)s %(levelname)s [%(threadName)s] <name> (%(funcName)s:%(lineno)d) - %(message)s".replace("<name>", name)
        self.handler.setFormatter(logging.Formatter(format))
        self.addHandler(self.handler)

        #Roll log file if needed
        if os.path.exists(settings.LOG_FILENAME) and time.strftime("%d", time.localtime(os.path.getmtime(settings.LOG_FILENAME))) != time.strftime("%d", time.localtime(time.time())):
            try:
                os.rename(settings.LOG_FILENAME, settings.LOG_FILENAME + "." + time.strftime("%Y-%m-%d"))
            except IOError:
                pass #Ignore IO exceptions

    @staticmethod
    def getLogger(name):
        """
        Return logger for a particular context name (typically the name of the main geoprocessing tool being executed).
        Logging level is specified in settings.py (LOG_LEVEL).

        :param name: Name of the context for logging
        """

        logging.setLoggerClass(ToolLogger)
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging,settings.LOG_LEVEL))
        return logger