import os
import logging
import logging.config

import settings


directory, filename = os.path.split(settings.LOG_FILENAME)
if not os.path.exists(directory):
    os.makedirs(directory)

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
            'filename': os.path.join(directory, filename),
            'when': "midnight",
            'delay': True,
            'backupCount': 10
        }
    },
    'loggers': {
        '': {
        'handlers': ['rotating_file_handler'],
        'level': settings.LOG_LEVEL
        }
    }
})
