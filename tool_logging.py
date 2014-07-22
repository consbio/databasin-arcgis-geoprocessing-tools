import os
import logging
import logging.config


LOG_FILENAME = "{0}/log/tools.log".format(os.path.dirname(__file__))
LOG_LEVEL = "DEBUG"


log_dir = os.path.dirname(LOG_FILENAME)
if not os.path.exists(log_dir):
    os.makedirs(log_dir)


logging.config.dictConfig({
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': "%(levelname)s %(asctime)s [%(thread)d] %(module)s (%(funcName)s:%(lineno)d) - %(message)s"
        }
    },
    'handlers': {
        'rotating_file_handler': {
            'formatter': "verbose",
            'class': "logging.handlers.TimedRotatingFileHandler",
            'filename': LOG_FILENAME,
            'when': "midnight",
            'delay': True,
            'backupCount': 10
        }
    },
    'loggers': {
        '': {
        'handlers': ['rotating_file_handler'],
        'level': LOG_LEVEL
        }
    }
})
