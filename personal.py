
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
# CELERY_TASK_ALWAYS_EAGER - default setting is True
#
# IF TRUE, run all tasks immediately, IN WEB CONTAINER
#
# IF FALSE, run delayed tasks async, IN THE WORKER CONTAINER
#
# NOTE - in order to send megatron_streaming events to kafka locally,
#        CELERY_TASK_ALWAYS_EAGER must be True
#
# NOTE - Strange errors often occur when CELERY_TASK_ALWAYS_EAGER is True.
#        For most cases prefer _____ CELERY_TASK_ALWAYS_EAGER = FALSE _____
#
#
CELERY_TASK_ALWAYS_EAGER = True
#
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#
MEGATRON_TASKS_ENABLED = True
#
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
###
# Avoid strange behavior due to replica lag when using the Production DB replica
# https://roverdotcom.atlassian.net/wiki/spaces/TECH/pages/395477248/The+Performance+Environment#ThePerformanceEnvironment-Overridedjangosettings
###
#
# REPLICA_DB_ALIAS = 'default'
#
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
# import os
# PTVSD_DEBUG = os.environ.get('PTVSD_DEBUG') == "1"
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
# Needed for developing metrics / dashboards / monitors locally
# https://roverdotcom.atlassian.net/wiki/spaces/TECH/pages/1120964125/Local+Development+of+Metrics+Dashboards+and+Monitors
#
# Use this to debug local statsd metrics to Rover.com-Dev organization
# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
# THREADSTATSD_DEVELOPER_TAG = 'adamp'
# STATSD_CLIENT = 'systems.datadog.statsd.ThreadStatsD'
#
# Use this to print out statsd metrics locally
# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
# STATSD_CLIENT = 'systems.statsd.pystatsd.PyStatsD'
# LOGGING = {
#     'version': 1,
#     'disable_existing_loggers': False,
#     'handlers': {
#         'console': {
#             'class': 'logging.StreamHandler',
#         },
#     },
#     'loggers': {
#         'systems.statsd.pystatsd': {
#             'handlers': ['console'],
#             'level': 'DEBUG',
#             'propagate': False,
#         },
#     }
# }
