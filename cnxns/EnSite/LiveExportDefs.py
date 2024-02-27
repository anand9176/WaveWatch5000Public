
# ==============================================================================

#

#  FILE: LiveExportDefs.py

#

# Common definitions for connecting to EnSiteX live export on rabbit mq

#

# ==============================================================================

 

# Connection parameters for localhost with SSL

BUS_PORT = 5671

# Enter your server hostname or IP address here
DEFAULT_BUS_HOST = '44.44.55.55'

BUS_VHOST = 'vh_live_export'

DEFAULT_APP_NAME = 'LiveExportPythonClientExample'

 

# AMQP configuration details

EXCHANGE_TYPE = 'fanout' # only one type of exchange is used

QUEUE_NAME = ''          # let rabbitmq choose the queue name

ROUTING_KEY = ''         # routing keys are not used

 

# Available exchanges (aka live export channels)

PRESENCE_EXCHANGE = 'HMB.PRESENCE'

CMD_EXCHANGE =      'EX.CMD'

LOC_EXCHANGE =      'EX.LOC'

BIP_LOC_EXCHANGE =  'EX.BIP_LOC'

ECG_RAW_EXCHANGE =  'EX.ECG_RAW'

ECG_FLT_EXCHANGE =  'EX.ECG_FLT'

UNI_RAW_EXCHANGE =  'EX.UNI_RAW'

UNI_FLT_EXCHANGE =  'EX.UNI_FLT'

BIP_RAW_EXCHANGE =  'EX.BIP_RAW'

BIP_FLT_EXCHANGE =  'EX.BIP_FLT'

# CS added surf:
SURF_EXCHANGE =  'EX.SURF'

# live export channel subscriptions, by default subscribe to all

DEFAULT_SUBSCRIPTIONS = [

    # CS added surf:
    SURF_EXCHANGE,

    PRESENCE_EXCHANGE,

    CMD_EXCHANGE,

    LOC_EXCHANGE,

    BIP_LOC_EXCHANGE,

    #ECG_RAW_EXCHANGE,

    ECG_FLT_EXCHANGE,

    #UNI_RAW_EXCHANGE,

    UNI_FLT_EXCHANGE,

    #BIP_RAW_EXCHANGE,

    BIP_FLT_EXCHANGE

]


PROTO_CONTENT_TYPE = 'application/protobuf'

# Presence message publish interval (seconds)
#
PRESENCE_INTERVAL = 1