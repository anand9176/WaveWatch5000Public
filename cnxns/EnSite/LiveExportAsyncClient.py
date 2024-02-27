

# ==============================================================================
#
#  FILE: LiveExportAsyncClient.py
#
# This example script is adapted from the following sources (Abbott initially,
# then presently by current authors [see repository license information]):
# https://pika.readthedocs.io/en/1.2.0/examples/asynchronous_consumer_example.html
# https://pika.readthedocs.io/en/1.2.0/examples/asynchronous_publisher_example.html
#
# Please refer to Pika license for licensing information
#
# Tested on python 3.9.10, pika 1.3.2 OpenSSL 1.0.2u 20 Dec 2019
#
# 
# ==============================================================================


from . import LiveExportDefs

# Ggl protobuf 'proto' imports
from . import EnSiteExport_pb2
from . import messagebus_pb2# for eg presence message ps
USE_pyroBuff = False# ^^!! currently not used due to issues installing under OSX (speed not a limitting factor ATM, anyway)
if USE_pyroBuff:# pyrobuf-based
    # has this file gone missing? need to regen?
    from pyrobuf_generated import EnSiteExport_proto as EnSiteExport_pb2
    #print(EnSiteExport_pb2.pyrobuf_list.TypedList.__bases__)
    '''
    if self.dictionise:
        if USE_pyroBuff:
            dico = data.SerializeToDict()
        else:
            dico = MessageToDict(data)
    '''
from google.protobuf.json_format import MessageToDict

import pika
# from pika.exchange_type import ExchangeType # not available in pika 0.10.0-10
import numpy as np

import pickle, functools, logging, os, ssl, sys, uuid, math, getpass
from time import time as curTime
from pprint import pprint as pp, pformat as pf

 
LOG_FORMAT = ('%(levelname) -10s %(asctime)s %(name) -30s %(funcName) '
              '-35s %(lineno) -5d: %(message)s')
LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING, format=LOG_FORMAT)

thisFileDir = os.path.dirname(__file__)

# SSL/TSL Certificate locations
#
DEFAULT_ROOT_CA_CERT = (thisFileDir+ '/certs/RootCA.cer')
DEFAULT_CLIENT_CERT = (thisFileDir+ '/certs/3PClient.cer')
DEFAULT_CLIENT_KEY = (thisFileDir+ '/certs/3PClient.key')

DEFAULT_APP_NAME = LiveExportDefs.DEFAULT_APP_NAME + 'Async'

ecgChans = ['i', 'ii', 'iii', 'avr', 'avl', 'avf', 'v1', 'v2', 'v3', 'v4', 'v5', 'v6']

parserFuncs = {
    'sjm.pb.ex.LocData': EnSiteExport_pb2.LocData,
    'sjm.pb.ex.EcgData': EnSiteExport_pb2.EcgData,
    'sjm.pb.ex.BioData': EnSiteExport_pb2.BioData,
    'sjm.pb.ex.SurfaceUpdate': EnSiteExport_pb2.SurfaceUpdate
}

class LiveExportChannel():
    def __init__(self, exchange='', channel=''):
        self.exchange = exchange
        self.channel = channel
        self.consumer_tag = None

class LiveExportAsyncClient(object):
    """This is an example publisher/consumer that will handle unexpected interactions
    with RabbitMQ such as channel and connection closures.

    If RabbitMQ closes the connection, it will reopen it. You should
    look at the output, as there are limited reasons why the connection may
    be closed, which usually are tied to permission related issues or
    socket timeouts.

    It uses delivery confirmations and illustrates one way to keep track of
    messages that have been sent and if they've been confirmed by RabbitMQ.

    """

    def __init__(# ** (2 stars indicate functions that have been modified from the ~Abbott template)
            self,
            dumpPath, 
            bus_host, bus_port, 
            exchangesToSubscribeTo,
            privateKeyPass = False,
            external_onCnxnCB = None,
            frameBufferSz = None
        ):
        """Setup the example publisher object
        """

        self.localRabbit = (bus_host in ('localhost', '127.0.0.1'))
        self.logChannel_uniFlt = []# a single channel of the UNI_FLT exchange, whole log length
        
        self.buff_hz = 100# ^^!! ...this is the packet rate! some packet's contain 20 sub-samples (making for an effective 2000Hz)
        if frameBufferSz is None:
            self.buff_secs = 6
        else:
            self.buff_secs = int(frameBufferSz / self.buff_hz)
        
        self.frameBufferSz = self.buff_secs * self.buff_hz
        
        self.exchangesToSubscribeTo = exchangesToSubscribeTo
        print('self.exchangesToSubscribeTo:', self.exchangesToSubscribeTo)
        
        self.external_onCnxnCB = external_onCnxnCB
        
        self.tmPntBuffer = {}
        self.first_tmPnt = None
        self.logFileTmLength = 2.880000114440918
        self.logFirstTmPnt = 1649693042.7693226
        self.firstFullSet = True
        self.firstMsgTime = None
        
        self.dumpFiles = False
        self.dumpFile = None
        self.cur_filePath = None
        self.dumpPath = dumpPath
        self.dumpFiles_payload = True
        self.dumpFilesInExFolders = False
        self.nbFramesPerWrite = 200
        assert(self.nbFramesPerWrite <= self.frameBufferSz*0.5)# ^^!! - nbFramesPerWrite must be smaller than half the frameBufferSz, as we write starting from nbFramesPerWrite frames back from the front edge (leadingEdgeBufferIdx)...
        self.nbFramesPerFile = self.nbFramesPerWrite * 5# ensure is a multiple of self.nbFramesPerWrite
        self.addExchangeToFile = True

        self.dumpMsgFPS = False
        self.dumpTimings = True
        self.msg_tmAccum = 0
        self.msgsRecvd = 0
        self.msg_lastTm = curTime()
        self.lightMsgProcessing = False
        self.new = True
        self.pullSampleTime = False
        self.tmStamp_isSamples = False
        self.tmStamp_sampleTm_isMsgLag = True
        self.tmStamp_relToSt = True
        self.protoParse = True
        self.dictionise = True
        self.firstSampleTime_sec = None
        # self.exchangeEntities = dict([(ex, None) for ex in LiveExportDefs.DEFAULT_SUBSCRIPTIONS])
        self.nbExchanges = None
       
        self.globalFrame = -1
        self.dumpFrameTicker = 0
        self.leadingEdgeBufferIdx = -1
        self.frameTms = [None,] * self.frameBufferSz * 2# ^^!! is doubled, for same reason we do it for .samples[], see notes there
        self.samples = []#[False,]*self.frameBufferSz# filled w False initially, as None has special meaning of 'tm/slot/frame has been seen for atleast one exchange, but not this one'
        self.samples_struct = {}
        self.chans_byIdx = []
        self.encounterSniffIdx = 0

        self.totalNbVoltChans = 0
        self.totalNbLocChans = 0

        self.preRecSniff = True
        self.preRecSniff_stage = 0
        self.preRecSniff_stageSniffs = 80 
        self.cur_stageSniffs = 0

        self.failedCnxn = False
        
        self._privateKeyPass = privateKeyPass#^^!! you dont NEED to pass this, and have in memory, you can enter it each time

        # base pika cnxn mechanics...
        #

        self._connection = None
        self._channel = None

        self._deliveries = None
        self._acked = None
        self._nacked = None
        self._message_number = None

        self._stopping = False
        self._live_export_channels = []
        self._session_uuid = None
        self._consuming = False
        self._prefetch_count = 1

        self._presenceEnabled = False

        if not self.localRabbit:

            if not os.path.isfile(DEFAULT_ROOT_CA_CERT):
                LOGGER.warning('Root CA Certificate path invalid: %s', DEFAULT_ROOT_CA_CERT)
                sys.exit(1)

            if not os.path.isfile(DEFAULT_CLIENT_CERT):
                LOGGER.warning('Client Certificate path invalid: %s', DEFAULT_CLIENT_CERT)
                sys.exit(1)

            if not os.path.isfile(DEFAULT_CLIENT_KEY):
                LOGGER.warning('Client key path invalid: %s', DEFAULT_CLIENT_KEY)
                sys.exit(1)
        
        self._bus_host = bus_host
        self._bus_port = bus_port
    
    def resetSampleAquisition(self):
        
        if 0:
            
            self.firstMsgTime = None
            
            self.msgsRecvd = 0
            self.msg_lastTm = curTime()
            
            self.pullSampleTime = False
            self.tmStamp_isSamples = False
            self.tmStamp_sampleTm_isMsgLag = True
            self.tmStamp_relToSt = True
            
            self.protoParse = True
            self.dictionise = True
            self.firstSampleTime_sec = None
            # self.exchangeEntities = dict([(ex, None) for ex in LiveExportDefs.DEFAULT_SUBSCRIPTIONS])
            self.nbExchanges = None
        
            self.globalFrame = -1
            self.dumpFrameTicker = 0
            self.leadingEdgeBufferIdx = -1
            self.frameTms = [None,] * self.frameBufferSz * 2# ^^!! is doubled, for same reason we do it for .samples[], see notes there
            self.samples = []#[False,]*self.frameBufferSz# filled w False initially, as None has special meaning of 'tm/slot/frame has been seen for atleast one exchange, but not this one'
            self.samples_struct = {}
            self.chans_byIdx = []
            self.encounterSniffIdx = 0

            self.totalNbVoltChans = 0
            self.totalNbLocChans = 0

        self.preRecSniff = True
        self.preRecSniff_stage = 0
        self.preRecSniff_stageSniffs = 80 
        self.cur_stageSniffs = 0
        
    
    def getChannel(self, exchange_name):
        """Helper function to access live export channels
        """
        for channel in self._live_export_channels:
            if channel.exchange == exchange_name:
                return channel
        LOGGER.warning('No LiveExportChannel found with exchange name %s', exchange_name)
        return LiveExportChannel() # return an empty object

    def connect(self):# **
        """This method connects to RabbitMQ, returning the connection handle.
        When the connection is established, the on_connection_open method
        will be invoked by pika.
 
        :rtype: pika.SelectConnection
 
        """
        LOGGER.info('Connecting to host %s on port %s and vhost %s',
            self._bus_host,
            LiveExportDefs.BUS_PORT,
            LiveExportDefs.BUS_VHOST)
 
        self._session_uuid = str(uuid.uuid4())
        
        if self.localRabbit:
            
            print('>> overidding to a localRabbit cnxn')
            param = pika.ConnectionParameters(
                host = self._bus_host,# will be localhost/~127.0.0.1 for local
                port = self._bus_port,# will be 5672 for local
                virtual_host = LiveExportDefs.BUS_VHOST,
                credentials = pika.credentials.PlainCredentials('guest', 'guest'),
                connection_attempts = 2
            )
            
        else:
            
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
            ctx.load_verify_locations(DEFAULT_ROOT_CA_CERT)
            ctx.verify_mode = ssl.CERT_REQUIRED
            ctx.load_cert_chain(
                DEFAULT_CLIENT_CERT,
                DEFAULT_CLIENT_KEY,
                password = None if self._privateKeyPass == False else self._privateKeyPass if self._privateKeyPass != True else getpass.getpass('private key password: ')
            )
            ssl_options = pika.SSLOptions(context = ctx)
            
            param = pika.ConnectionParameters(
                host = self._bus_host,
                port = LiveExportDefs.BUS_PORT,
                virtual_host = LiveExportDefs.BUS_VHOST,
                ssl_options = ssl_options,
                credentials = pika.credentials.ExternalCredentials(),
                connection_attempts = 3
            )
        
        return pika.SelectConnection(
            parameters = param,
            on_open_callback = self.on_connection_open,
            on_open_error_callback = self.on_connection_open_error,
            on_close_callback = self.on_connection_closed
        )

    def on_connection_open(self, _unused_connection):# **
        """This method is called by pika once the connection to RabbitMQ has
        been established. It passes the handle to the connection object in
        case we need it, but in this case, we'll just mark it unused.
 
        :param pika.SelectConnection _unused_connection: The connection
 
        """
        LOGGER.info('Connection opened')
        print('---> Connection opened')
        self.cnxnEstablished = True
        if self.external_onCnxnCB is not None:
            self.external_onCnxnCB()
        self.open_channel()

    def on_connection_open_error(self, _unused_connection, err):
        """This method is called by pika if the connection to RabbitMQ
        can't be established.
 
        :param pika.SelectConnection _unused_connection: The connection
        :param Exception err: The error
 
        """
        LOGGER.error('Connection open failed, reopening in 5 seconds: %s', err)
        self.failedCnxn = True
        self._connection.ioloop.call_later(5, self._connection.ioloop.stop)

    def on_connection_closed(self, _unused_connection, reason):
        """This method is invoked by pika when the connection to RabbitMQ is
        closed unexpectedly. Since it is unexpected, we will reconnect to
        RabbitMQ if it disconnects.
 
        :param pika.connection.Connection _unused_connection: The closed connection obj
        :param int reason_code: code corresponding to reason for channel close
        :param string reason_text: string corresponding to reason for channel close
 
        Signature in latest version of pika is on_connection_closed(self, _unused_connection, reason)
        :param Exception reason: exception representing reason for loss of
            connection.
 
        """
        self._channel = None
        if self._stopping:
            self._connection.ioloop.stop()
        else:
            LOGGER.warning('Connection closed, reopening in 5 seconds: %s', reason)
            self._connection.ioloop.call_later(5, self._connection.ioloop.stop)

    def open_channel(self):
        """This method will open a new channel with RabbitMQ by issuing the
        Channel.Open RPC command. When RabbitMQ confirms the channel is open
        by sending the Channel.OpenOK RPC reply, the on_channel_open method
        will be invoked.
 
        """
        LOGGER.info('Creating a new channel')
        self._connection.channel(on_open_callback=self.on_channel_open)

    def on_channel_open(self, channel):
        """This method is invoked by pika when the channel has been opened.
        The channel object is passed in so we can make use of it.
 
        Since the channel is now open, we'll declare the exchange to use.
 
        :param pika.channel.Channel channel: The channel object
 
        """
        LOGGER.info('Channel opened')
        self._channel = channel
        self.add_on_channel_close_callback()
 
        # Set up exchanges, queues, and consume for all exchanges
        for exchange in self.exchangesToSubscribeTo:
            self.setup_exchange(exchange)

    def add_on_channel_close_callback(self):
        """This method tells pika to call the on_channel_closed method if
        RabbitMQ unexpectedly closes the channel.
 
        """
        LOGGER.info('Adding channel close callback')
        self._channel.add_on_close_callback(self.on_channel_closed)

    def on_channel_closed(self, channel, reply_code):
        """Invoked by pika when RabbitMQ unexpectedly closes the channel.
        Channels are usually closed if you attempt to do something that
        violates the protocol, such as re-declare an exchange or queue with
        different parameters. In this case, we'll close the connection
        to shutdown the object.
 
        :param pika.channel.Channel channel: The closed channel
        :param int reply_code: code corresponding to reason for channel close
        :param string reply_text: string corresponding to reason for channel close
 
        Signature in latest version of pika is on_channel_closed(self, channel, reason)
        :param Exception reason: why the channel was closed
 
        """
        LOGGER.warning('Channel %i was closed with code %s', channel, reply_code)

        self._channel = None
        if not self._stopping:
            self._connection.close()

    def setup_exchange(self, exchange_name):
        """Setup the exchange on RabbitMQ by invoking the Exchange.Declare RPC
        command. When it is complete, the on_exchange_declareok method will
        be invoked by pika.
 
        :param str|unicode exchange_name: The name of the exchange to declare
 
        """
        LOGGER.info('Declaring exchange "%s"', exchange_name)
 
        # Note: functools.partial demonstrates how arbitrary data
        # can be passed to the callback when it is called
        self._channel.exchange_declare(
            exchange = exchange_name,
            exchange_type = LiveExportDefs.EXCHANGE_TYPE,
            passive = True,
            callback = functools.partial(
                self.on_exchange_declareok,
                exchange_name = exchange_name))

    def on_exchange_declareok(self, _unused_frame, exchange_name):
        """Invoked by pika when RabbitMQ has finished the Exchange.Declare RPC
        command.
 
        :param pika.Frame.Method unused_frame: Exchange.DeclareOk response frame
        :param str|unicode userdata: Extra user data (exchange name)
 
        """
        LOGGER.info('Exchange declared: "%s"', exchange_name)
        self.setup_queue(LiveExportDefs.QUEUE_NAME, exchange_name)

    def setup_queue(self, queue_name, exchange_name):
        """Setup the queue on RabbitMQ by invoking the Queue.Declare RPC
        command. When it is complete, the on_queue_declareok method will
        be invoked by pika.
 
        :param str|unicode queue_name: The name of the queue to declare.
 
        """
        LOGGER.info('Declaring queue "%s" for exchange "%s"', queue_name, exchange_name)
 
        self._channel.queue_declare(
            queue = queue_name,
            passive = False,
            exclusive = True,
            auto_delete = True,
            callback = functools.partial(
                self.on_queue_declareok,
                exchange_name = exchange_name))

    def on_queue_declareok(self, method_frame, exchange_name):
        """Method invoked by pika when the Queue.Declare RPC call made in
        setup_queue has completed. In this method we will bind the queue
        and exchange together with the routing key by issuing the Queue.Bind
        RPC command. When this command is complete, the on_bindok method will
        be invoked by pika.
 
        :param pika.frame.Method method_frame: The Queue.DeclareOk frame
 
        """
        queue_name = method_frame.method.queue
        LOGGER.info('Binding exchange "%s" to queue "%s" with routing key "%s"',
                    exchange_name,
                    queue_name,
                    LiveExportDefs.ROUTING_KEY)
 
        self._channel.queue_bind(
            queue = queue_name,
            exchange = exchange_name,
            routing_key = LiveExportDefs.ROUTING_KEY,
            callback = functools.partial(
                self.on_bindok,
                exchange_name = exchange_name,
                queue_name = queue_name))

    def on_bindok(self, _unused_frame, exchange_name, queue_name):
        """This method is invoked by pika when it receives the Queue.BindOk
        response from RabbitMQ. Since we know we're now setup and bound, it's
        time to start publishing.
       
        """
        LOGGER.info('Queue "%s" bound to exchange %s',
            queue_name,
            exchange_name)
 
        # create the live export channel object
        self._live_export_channels.append(LiveExportChannel(exchange_name, queue_name))
 
        self.start_publishing_presence(exchange_name)
        self.set_qos(exchange_name, queue_name)

    def start_publishing_presence(self, exchange_name):
        """This method will enable delivery confirmations and schedule the
        first presence message to be sent to RabbitMQ
 
        """
        # start presence message
        if not self._presenceEnabled and exchange_name is LiveExportDefs.PRESENCE_EXCHANGE:
            self._presenceEnabled = True
 
            LOGGER.info('Start publishing the presence message')
 
            self.enable_delivery_confirmations()
            self.schedule_next_presence_message()

    def enable_delivery_confirmations(self):
        """Send the Confirm.Select RPC method to RabbitMQ to enable delivery
        confirmations on the channel. The only way to turn this off is to close
        the channel and create a new one.
 
        When the message is confirmed from RabbitMQ, the
        on_delivery_confirmation method will be invoked passing in a Basic.Ack
        or Basic.Nack method from RabbitMQ that will indicate which messages it
        is confirming or rejecting.
 
        """
        LOGGER.info('Issuing Confirm.Select RPC command')
        self._channel.confirm_delivery(self.on_delivery_confirmation)

    def on_delivery_confirmation(self, method_frame):
        """Invoked by pika when RabbitMQ responds to a Basic.Publish RPC
        command, passing in either a Basic.Ack or Basic.Nack frame with
        the delivery tag of the message that was published. The delivery tag
        is an integer counter indicating the message number that was sent
        on the channel via Basic.Publish. Here we're just doing house keeping
        to keep track of stats and remove message numbers that we expect
        a delivery confirmation of from the list used to keep track of messages
        that are pending confirmation.
 
        :param pika.frame.Method method_frame: Basic.Ack or Basic.Nack frame
 
        """
        confirmation_type = method_frame.method.NAME.split('.')[1].lower()
        LOGGER.info('Received %s for delivery tag: %i', confirmation_type,
                    method_frame.method.delivery_tag)
        if confirmation_type == 'ack':
            self._acked += 1
        elif confirmation_type == 'nack':
            self._nacked += 1
        self._deliveries.remove(method_frame.method.delivery_tag)
        LOGGER.info(
            'Published %i messages, %i have yet to be confirmed, '
            '%i were acked and %i were nacked',
            self._message_number,
            len(self._deliveries),
            self._acked,
            self._nacked)

    def schedule_next_presence_message(self):
        """If we are not closing our connection to RabbitMQ, schedule another
        message to be delivered in LiveExportDefs.PRESENCE_INTERVAL seconds.
 
        """
        LOGGER.info('Scheduling next message for %0.1f seconds',
                    LiveExportDefs.PRESENCE_INTERVAL)
        
        self._connection.ioloop.call_later(LiveExportDefs.PRESENCE_INTERVAL,
                                            self.publish_presence_message)

    def publish_presence_message(self):
        """If the class is not stopping, publish a message to RabbitMQ,
        appending a list of deliveries with the message number that was sent.
        This list will be used to check for delivery confirmations in the
        on_delivery_confirmations method.
 
        Once the message has been sent, schedule another message to be sent.
 
        """
        if self._channel is None or not self._channel.is_open:
            return
 
        message = messagebus_pb2.PresenceMessage()
        message.status = 2 # Ready
        # device_type must be unique among all devices connected to rabbitmq
        message.device_type = DEFAULT_APP_NAME
        message.device_name = DEFAULT_APP_NAME
        message.serial_number = 'xyz789' # This should be a unique ID derived from the certificate
        message.subscribed_channels[:] = self.exchangesToSubscribeTo
        message.heartbeat_frequency = 1000 # units ms
        message.heartbeat_threshold = 3
 
        self._channel.basic_publish(
            exchange = LiveExportDefs.PRESENCE_EXCHANGE,
            routing_key = LiveExportDefs.ROUTING_KEY,
            body = message.SerializeToString(),
            properties = pika.BasicProperties(
                type = message.DESCRIPTOR.full_name,
                content_type = LiveExportDefs.PROTO_CONTENT_TYPE,
                message_id = str(uuid.uuid4()),
                app_id = DEFAULT_APP_NAME))
 
        self._message_number += 1
        self._deliveries.append(self._message_number)
        LOGGER.info('Published presence message # %i', self._message_number)
        self.schedule_next_presence_message()

    def set_qos(self, exchange_name, queue_name):
        """This method sets up the consumer prefetch to only be delivered
        one message at a time. The consumer must acknowledge this message
        before RabbitMQ will deliver another one. You should experiment
        with different prefetch values to achieve desired performance.
 
        """
        # Note that this will be done once for every exchange in
        #  LiveExportDefs.DEFAULT_SUBSCRIPTIONS which is redundant but okay
        LOGGER.info('Setting QOS with exchange %s and queue %s',
            exchange_name,
            queue_name)
 
        self._channel.basic_qos(
            prefetch_count = self._prefetch_count,
            callback = functools.partial(
                self.on_basic_qos_ok,
                exchange_name = exchange_name,
                queue_name = queue_name))

    def on_basic_qos_ok(self, _unused_frame, exchange_name, queue_name):
        """Invoked by pika when the Basic.QoS method has completed. At this
        point we will start consuming messages by calling start_consuming
        which will invoke the needed RPC commands to start the process.
        :param pika.frame.Method _unused_frame: The Basic.QosOk response frame
 
        """
        LOGGER.info('QOS set to: %d with exchange %s and queue %s',
            self._prefetch_count,
            exchange_name,
            queue_name)
 
        self.start_consuming(exchange_name, queue_name)

    def start_consuming(self, exchange_name, queue_name):
        """This method sets up the consumer by first calling
        add_on_cancel_callback so that the object is notified if RabbitMQ
        cancels the consumer. It then issues the Basic.Consume RPC command
        which returns the consumer tag that is used to uniquely identify the
        consumer with RabbitMQ. We keep the value to use it when we want to
        cancel consuming. The on_message method is passed in as a callback pika
        will invoke when a message is fully received.
 
        """
        LOGGER.info('Start consuming on exchange %s with queue %s',
            exchange_name,
            queue_name)
           
        # Note that this will be done once for every exchange in
        #  LiveExportDefs.DEFAULT_SUBSCRIPTIONS which is redundant but okay
        self.add_on_cancel_callback()
 
        # Start consuming on the queue. This will be done once for every
        # exchange/queue in LiveExportDefs.DEFAULT_SUBSCRIPTIONS which is what we want
        tag = self._channel.basic_consume(
            queue = queue_name,
            on_message_callback = functools.partial(# consumer_callback was older pika
                self.on_message,
                exchange_name = exchange_name))
        self.getChannel(exchange_name).consumer_tag = tag

    def add_on_cancel_callback(self):
        """Add a callback that will be invoked if RabbitMQ cancels the consumer
        for some reason. If RabbitMQ does cancel the consumer,
        on_consumer_cancelled will be invoked by pika.
 
        """
        LOGGER.info('Adding consumer cancellation callback')
        self._channel.add_on_cancel_callback(self.on_consumer_cancelled)

    def on_consumer_cancelled(self, method_frame):
        """Invoked by pika when RabbitMQ sends a Basic.Cancel for a consumer
        receiving messages.
        :param pika.frame.Method method_frame: The Basic.Cancel frame
 
        """
        LOGGER.info('Consumer was cancelled remotely, shutting down: %r',
                    method_frame)
        if self._channel:
            self._channel.close()

    def on_message(self, _unused_channel, basic_deliver, properties, body, exchange_name):# **
        """Invoked by pika when a message is delivered from RabbitMQ. The
        channel is passed for your convenience. The basic_deliver object that
        is passed in carries the exchange, routing key, delivery tag and
        a redelivered flag for the message. The properties passed in is an
        instance of BasicProperties with the message properties and the body
        is the message that was sent.
        :param pika.channel.Channel _unused_channel: The channel object
        :param pika.Spec.Basic.Deliver: basic_deliver method
        :param pika.Spec.BasicProperties: properties
        :param bytes body: The message body
 
        """
        
        if 0:
            #LOGGER.info('Received message # %s from %s on exchange %s, and looped Log this many times: %s',
            print('Received message # %s from %s on exchange %s, and looped Log this many times: %s',
                basic_deliver.delivery_tag,
                properties.app_id,
                exchange_name,
                properties.cluster_id# CS (for when using dummy logSender from local rabbit server)
            )
        
        if exchange_name == LiveExportDefs.PRESENCE_EXCHANGE:# dont need to skip SURF at this stage as it isnt in default list of subs
            self.acknowledge_message(basic_deliver.delivery_tag)
            return
        
        
        if exchange_name == LiveExportDefs.SURF_EXCHANGE:
            
            data = parserFuncs[properties.type]()# instantiate appropriate parser for the recvd message type
            data.ParseFromString(body)# see EnSiteExport.proto for message data's structure
            '''
            message SurfaceUpdate
            {
                SurfaceUpdateType type = 1;
                repeated float vertices = 2;
                repeated float normals = 3;
                repeated SurfaceAttribs surfaces = 4;
            }
            
            enum SurfaceUpdateType
            {
                none = 0;          // No update
                all = 1;           // All surfaces are being updated, any missing are presumed deleted
                attrib = 2;        // Attribute-only update for all surfaces, no surface polygon data, missing ID means deleted
                edit = 3;          // Update to only the surface currently being edited
                no_edit = 4;       // Update to surfaces not being edited
            }
            
            message SurfaceAttribs
            {
                int32 id = 1;
                Color4 color = 2;
                string name = 3;
                repeated uint32 triangle_indices = 4;
            }
            
            '''
            #print('\n\n ---->>> srf exchg, SurfaceUpdateType:', data.type, '\n\n')
            
            if data.type == 4:# 4 == no_edit
                print('surf datas...')
                
                print('vrts:', data.vertices[:5])
                print('nrms:', data.normals[:5])
                with open('vrts.pkl', 'wb') as f: pickle.dump(list(data.vertices), f)
                with open('nrms.pkl', 'wb') as f: pickle.dump(list(data.normals), f)
                
                if data.surfaces:
                    print('has srf attribs:')
                    for idx, srfAttrib in enumerate(data.surfaces):
                        #print(dir(data.surfaces[0]))
                        print('srf idx:', str(idx))
                        print('srfAttrib.id:', srfAttrib.id)
                        print('srfAttrib.color:', srfAttrib.color)
                        print('srfAttrib.name:', srfAttrib.name)
                        print('srfAttrib.triangle_indices:', srfAttrib.triangle_indices[:5])
                        with open('tri.pkl', 'wb') as f: pickle.dump(list(srfAttrib.triangle_indices), f)
            
            self.acknowledge_message(basic_deliver.delivery_tag)
            return
        
        if self.firstMsgTime is None: self.firstMsgTime = curTime()

        # check out the structure of the data for the current catheter configuration,
        # and then go forth collecting samples assuming that will be consistent (but 
        # need to also implement checking periodically that is the case?)
        #
        if self.preRecSniff:
            
            if 0:
                print(self.preRecSniff_stage, ' pre-rec stage sniff...')
                print('properties.type:', properties.type)
                print('parserFuncs[properties.type]', parserFuncs[properties.type])
            
            data = parserFuncs[properties.type]()# instantiate appropriate parser for the recvd message type
            data.ParseFromString(body)# see EnSiteExport.proto for message data's structure
            tmPnt_0 = data.data[0]

            lastSniffOfStage = (self.cur_stageSniffs >= self.preRecSniff_stageSniffs)

            if self.preRecSniff_stage == 0:
                # collect the broadcasting exchanges, and their catheter structures
                #
                
                if exchange_name not in self.samples_struct:
                    
                    self.samples_struct[exchange_name] = {}
                    self.samples_struct[exchange_name]['cath_gIdxSt'] = []
                    
                    isLoc = (properties.type == 'sjm.pb.ex.LocData')
                    # non-Loc exchanges pack 20 'sub' tm samples, per 100Hz (for total 2000Hz). 
                    # Each .data is one of those subSamples
                    #
                    nb_subSamples = len(data.data)
                    if isLoc:
                        if nb_subSamples != 1:
                            LOGGER.warning('**---->  sjm.pb.ex.LocData doesnt have just 1 LocTimepoint data!?!')
                    else:# sjm.pb.ex.BioData/EcgData
                        if nb_subSamples != 20:
                            LOGGER.warning('**---->  sjm.pb.ex.BioData/EcgData doesnt carry 20 xTimepoint datas!?!')
                    
                    # collect the catheters and chans. These are ordered the same in each message (we dbl check during sniff)
                    #
                    if properties.type in ('sjm.pb.ex.LocData', 'sjm.pb.ex.BioData'):
                        
                        caths_andTheirChans = []# ordered
                        for cathIdx, cath in enumerate(tmPnt_0.catheter):
                            
                            self.samples_struct[exchange_name]['cath_gIdxSt'].append(self.encounterSniffIdx)

                            cath_chans = []
                            for chan in cath.channel:
                                cath_chans.append(chan.label)

                                self.chans_byIdx.append(
                                    (exchange_name, cath.name, chan.label)
                                )

                                self.encounterSniffIdx += 1
                            
                            caths_andTheirChans.append(
                                (
                                    cath.name,
                                    cath_chans[:]# cpy
                                )
                            )
                        
                        
                        # dbl check that each subSample tmPnt carries the same catheter set
                        # (so in future we need only look at first one, [0], for structure)
                        #
                        for tmPnt in data.data:
                            otherTmPnt_caths_andTheirChans = []
                            for cath in tmPnt.catheter:
                                cath_chans = []
                                for chan in cath.channel:
                                    cath_chans.append(chan.label)
                                otherTmPnt_caths_andTheirChans.append(
                                    (
                                        cath.name,
                                        cath_chans[:]# cpy
                                    )
                                )
                            if otherTmPnt_caths_andTheirChans != caths_andTheirChans:
                                LOGGER.warning('**---->  not all subSample tm pnts carry catheter listings in same pattern!?!')

                    else:# EcgData
                        
                        self.samples_struct[exchange_name]['cath_gIdxSt'].append(self.encounterSniffIdx)
                        
                        caths_andTheirChans = [('ECG', ecgChans),]# 'catheter', just an honoury one for code simplicity (less branching, etc)
                        
                        for ecgChan in ecgChans:
                            self.chans_byIdx.append(
                                (exchange_name, 'ECG', ecgChan)# again, ECG treated as an honoury catheter
                            )
                            self.encounterSniffIdx += 1


                    # store this at-time-of-sniffing structure of sample data (so we can throw away the massive redundancy of this in each and every sample messge sent by DWS)
                    #
                    self.samples_struct[exchange_name]['idx'] = (len(self.samples_struct) - 1)# exchanges given an index based on when they are first encountered/sniffed out
                    self.samples_struct[exchange_name]['nb_subSamples'] = nb_subSamples# 1 or 20
                    self.samples_struct[exchange_name]['sampleType'] = properties.type
                    self.samples_struct[exchange_name]['isLoc'] = isLoc
                    self.samples_struct[exchange_name]['caths'] = caths_andTheirChans# should always be in same order... (we check below, atleast for 'a while')
                    self.samples_struct[exchange_name]['lastFilledIdx'] = -1# tracks where in the rolling buffer we are up to, for this exchange
                    # the following are only used during sniffing...
                    self.samples_struct[exchange_name]['lastSampleData'] = None
                    self.samples_struct[exchange_name]['lastTmStamp'] = -1
                    self.samples_struct[exchange_name]['nonTemporallyAligning'] = []
                    self.samples_struct[exchange_name]['last5TmPnts'] = []
                
                if lastSniffOfStage:
                    
                    # 'reverse' look up to go from (exchName, cathName, chanName) to the chan's global idx
                    #
                    self.chans_gIdxLUp = dict( [(chan, gIdx) for gIdx, chan in enumerate(self.chans_byIdx)] )
                    
                    # store counts of chan types (LOC vs electro)
                    # used for different display treatments
                    #
                    for exchgName, exchg in self.samples_struct.items():
                        for cath in exchg['caths']:
                            if exchgName.endswith('LOC'):
                                self.totalNbLocChans += len(cath[1])
                            else:
                                self.totalNbVoltChans += len(cath[1])
                    
                    # allocate numpy arrays (the rolling buffers)
                    #
                    nbChans = len(self.chans_byIdx)
                    #below, the *2 is for handling wrapping on buffer edges (sacrifice memory and an extra copy op for faster, contiguous-memory arr views/slices)
                    a_locArr = np.empty((self.frameBufferSz * 2, 3))# each 100Hz frame carries a single xyz loc
                    a_valArr = np.empty((self.frameBufferSz * 2, 20))# each 100Hz frame carries 20 'sub samples'
                    self.samples = [None,] * nbChans# ie, a flat array of ALL chans of data (heirachical structure is stripped out, reconstituable from info scraped into self.samples_struct)
                    for gIdx, chan in enumerate(self.chans_byIdx):
                        chan_exchg = chan[0]
                        isLoc = self.samples_struct[chan_exchg]['isLoc']
                        self.samples[gIdx] = a_locArr.copy() if isLoc else a_valArr.copy()
                    
                    self.preRecSniff_stage += 1
                    self.cur_stageSniffs = 0
                    # nb sniffs in next stage?
                    self.preRecSniff_stageSniffs = 80

            elif self.preRecSniff_stage == 1:
                # check the collected samples structure is remaining stable...
                #
                
                exchgStruct = self.samples_struct[exchange_name]

                nb_subSamples = len(data.data)
                if nb_subSamples != exchgStruct['nb_subSamples']:
                    LOGGER.warning('**---->  nb_subSamples varying between messages!? %s', exchange_name)

                # are the caths varying?
                #
                if properties.type in ('sjm.pb.ex.LocData', 'sjm.pb.ex.BioData'):
                    
                    caths_andTheirChans = []# ordered
                    for cath in tmPnt_0.catheter:
                        cath_chans = []
                        for chan in cath.channel:
                            cath_chans.append(chan.label)
                        caths_andTheirChans.append(
                            (
                                cath.name,
                                cath_chans[:]# cpy
                            )
                        )
                    
                    if exchgStruct['caths'] != caths_andTheirChans:
                        LOGGER.warning('**---->  catheters and their channel names varying between messages!? %s', exchange_name)

                else:# EcgData
                    pass
                    # is a stable-table
                    #
                
                if lastSniffOfStage:
                    self.nbExchanges = len(self.samples_struct)
                    self.preRecSniff_stage += 1
                    self.cur_stageSniffs = 0
                    # nb sniffs in next stage?
                    self.preRecSniff_stageSniffs = 400# a lot more sniffs!
                
            elif self.preRecSniff_stage == 2:
                # ? check tm differences between samples on each channel, make sure about ~0.01/100hz
                #
                
                exchgStruct = self.samples_struct[exchange_name]
                
                sampleTm_sec = 0.000001 * tmPnt_0.t.microseconds + tmPnt_0.t.seconds

                lastTmStamp = exchgStruct['lastTmStamp']
                if lastTmStamp != -1:
                    tmStep = sampleTm_sec - lastTmStamp
                    if not math.isclose(tmStep, 0.01, rel_tol=1e-4):
                        LOGGER.warning('**---->  the tmStep between samples appears to not be ~0.01/100Hz, %s, for %s!?', tmStep, exchange_name)
                
                exchgStruct['lastTmStamp'] = sampleTm_sec
                
                if lastSniffOfStage:
                    # nb sniffs in next stage?
                    self.preRecSniff_stage += 1
                    self.cur_stageSniffs = 0
                    self.preRecSniff_stageSniffs = 100
                
            elif self.preRecSniff_stage == 3:
                # look for large temporal missalignments between channels (i've seen this with LOC)
                #
                
                sampleTm_sec = 0.000001 * tmPnt_0.t.microseconds + tmPnt_0.t.seconds
                if self.localRabbit and True:
                    # make time continuous, from a looping log...
                    # reqs editing the message object's Timestamp(s)... prob expensive?
                    #
                    curLogLoopTmOffset = float(properties.cluster_id) * self.logFileTmLength# cluster_id == self.nbOfLogLoops over in LogSender
                    sampleTm_sec += curLogLoopTmOffset
                    
                    # stick it back in data here as we store that in 'lastSampleData', and may later pull the time out again
                    #
                    data.data[0].t.seconds = math.floor(sampleTm_sec)
                    data.data[0].t.microseconds = int((sampleTm_sec % 1) / 0.000001)
                
                
                exchgStruct = self.samples_struct[exchange_name]
                if 'last5TmPnts' not in exchgStruct:  exchgStruct['last5TmPnts'] = []
                last5TmPnts = exchgStruct['last5TmPnts']
                if len(last5TmPnts) < 5:
                    last5TmPnts.append(sampleTm_sec)
                
                # start saving last sample seen, ready for tm alignment next
                #
                exchgStruct['lastSampleData'] = data# we make fresh data objs each msg received, so no need to cpy, etc
                exchgStruct['lastTmStamp'] = sampleTm_sec
                
                
                if lastSniffOfStage:
                    
                    # check that tm pnts are snappable (within a tolerance) between exchanges
                    #
                    for ex in self.samples_struct:
                        if len(self.samples_struct[ex]['last5TmPnts']) != 5:
                            LOGGER.warning('**---->  unable to collect 5 tmPnt samples for %s, over this number of received msgs: %s!?', ex, self.preRecSniff_stageSniffs)
                    
                    atLeastOneExNotTemporallyAligning = False
                    for ex in self.samples_struct:
                        self.samples_struct[ex]['nonTemporallyAligning'] = []
                        last5TmPnts = self.samples_struct[ex]['last5TmPnts']
                        middleTmPnt = last5TmPnts[2]
                        for other_ex in self.samples_struct:
                            if other_ex == ex: continue
                            other_last5TmPnts = self.samples_struct[other_ex]['last5TmPnts']
                            valueSnap = 0
                            smallestValDif = 1.
                            for other_last5TmPnt in other_last5TmPnts:
                                if math.isclose(middleTmPnt, other_last5TmPnt, rel_tol=1e-4):
                                    valueSnap = 1
                                    break
                                dif = abs(other_last5TmPnt - middleTmPnt)
                                if dif < smallestValDif:
                                    smallestValDif = dif
                            
                            if not valueSnap:
                                self.samples_struct[ex]['nonTemporallyAligning'].append(
                                    (other_ex, smallestValDif)
                                )
                                atLeastOneExNotTemporallyAligning = True
                    
                    if atLeastOneExNotTemporallyAligning:
                        LOGGER.warning('**---->  not all the exchanges are temporally aligned:')
                        for exchgName in self.samples_struct:
                            LOGGER.warning('... %s, with:', exchgName)
                            for otherEx in self.samples_struct[exchgName]['nonTemporallyAligning']:
                                LOGGER.warning('..... %s', otherEx)
                    

                    # find the most forward timepoint we've received, and call that 'frame 0' of the record
                    #
                    lastTmStamps = []
                    for exchgName in self.samples_struct:
                        lastTmStamps.append(self.samples_struct[exchgName]['lastTmStamp'])
                    max_lastTmStamp = max(lastTmStamps)

                    self.globalFrame = 0# will increment when we see next higher valued tm (that isnt close enough to snap back to current leading tm)
                    self.leadingEdgeBufferIdx = 0
                    self.frameTms[self.leadingEdgeBufferIdx] = max_lastTmStamp
                    # see notes elsewhere on looping buffer overflow, continguous memory
                    #
                    self.frameTms[self.leadingEdgeBufferIdx + self.frameBufferSz] = self.frameTms[self.leadingEdgeBufferIdx]

                    # store any of the exchanges that are on that leading front currently
                    #
                    for exchgName in self.samples_struct:
                        
                        exchgStruct = self.samples_struct[exchgName]

                        if math.isclose(max_lastTmStamp, exchgStruct['lastTmStamp'], abs_tol = 0.005):
                            
                            data = exchgStruct['lastSampleData']

                            if exchgStruct['sampleType'] == 'sjm.pb.ex.EcgData':
                                
                                gIdx_cathSt = exchgStruct['cath_gIdxSt'][0]# [0] - only 1 'honoury catheter'

                                for chanIdx, ecgChan in enumerate(ecgChans):
                                    gIdx = (gIdx_cathSt + chanIdx)
                                    for tmPntIdx, tmPnt in enumerate(data.data):
                                        chanTmPnt = getattr(tmPnt, ecgChan)
                                        self.samples[gIdx][self.leadingEdgeBufferIdx][tmPntIdx] = chanTmPnt.value#self.globalFrame
                                    # see notes elsewhere on looping buffer overflow, continguous memory
                                    #
                                    self.samples[gIdx][self.leadingEdgeBufferIdx + self.frameBufferSz] = self.samples[gIdx][self.leadingEdgeBufferIdx]
                                
                            else:

                                isLocData = exchgStruct['isLoc']
                                
                                for cathIdx, cath in enumerate(data.data[0].catheter):# other tmPnts have same cath-chan structure
                                    gIdx_cathSt = exchgStruct['cath_gIdxSt'][cathIdx]
                                    for chanIdx, chan in enumerate(cath.channel):
                                        gIdx = (gIdx_cathSt + chanIdx)
                                        for tmPntIdx, tmPnt in enumerate(data.data):# will be just 1, for Loc
                                            chanTmPnt = tmPnt.catheter[cathIdx].channel[chanIdx]
                                            if isLocData:
                                                self.samples[gIdx][self.leadingEdgeBufferIdx][:] = (chanTmPnt.x, chanTmPnt.y, chanTmPnt.z)
                                            else:
                                                self.samples[gIdx][self.leadingEdgeBufferIdx][tmPntIdx] = chanTmPnt.value#self.globalFrame
                                        # see notes elsewhere on looping buffer overflow, continguous memory
                                        #
                                        self.samples[gIdx][self.leadingEdgeBufferIdx + self.frameBufferSz] = self.samples[gIdx][self.leadingEdgeBufferIdx]
                            
                            exchgStruct['lastFilledIdx'] = self.leadingEdgeBufferIdx
                            
                        # else, it'll be coming soon

                        exchgStruct['lastSampleData'] = None
                    
                    
                    
                    # done with the various sniffing stages - start collecting samples (well, already started above for those exchanges currently on the leading edge)
                    #
                    self.preRecSniff = False
                    self.preRecSniff_stage = 0
                    # self.preRecSniff_stageSniffs = 80
                    
                    #pp(self.samples)
                    
                    LOGGER.info(' --> completed pre-rec sniff')
                    print('------- \n', pf(self.samples_struct))
                    caths = []
                    for ex in self.samples_struct:
                        cathNames = [cath[0] for cath in self.samples_struct[ex]['caths']]
                        for cathName in cathNames:
                            if cathName not in caths: caths.append(cathName)
                    print('caths present:', ', '.join(caths))
                    
            
            self.cur_stageSniffs += 1
            

            self.acknowledge_message(basic_deliver.delivery_tag)
            return

        # collect messages into rolling buffer, optionally dumping to disk
        #
        if self.new:
            
            data = parserFuncs[properties.type]()
            data.ParseFromString(body)# extract/parse message into data var (slightly odd handling arrangement)

            if self.localRabbit and True:
                # make time continuous, from a looping log...
                # reqs editing the message object's Timestamp(s)... prob expensive?
                #
                curLogLoopTmOffset = float(properties.cluster_id) * self.logFileTmLength# cluster_id == self.nbOfLogLoops over in LogSender
                
                #^^!! - we are only looking at first tmPnt atm
                #
                log_sampleTm_sec = 0.000001 * data.data[0].t.microseconds + data.data[0].t.seconds
                log_sampleTm_sec += curLogLoopTmOffset
                data.data[0].t.seconds = math.floor(log_sampleTm_sec)
                data.data[0].t.microseconds = int((log_sampleTm_sec % 1) / 0.000001)

            exchgStruct = self.samples_struct[exchange_name]
            exchgSamplesIdx = exchgStruct['idx']
            
            tmPnt_0 = data.data[0]# for the current packet of samples, just look at time of the first one (will only ever be one for some types like LOC)
            sampleTm_sec = 0.000001 * tmPnt_0.t.microseconds + tmPnt_0.t.seconds# reconstitute float time from the two ints
            
            # find which slot in the rolling buffer this message data should go...
            #
            bufferIdxToFill = None
            if 0:# older method to find the next/current bufferIdxToFill for the incoming exchange's message

                for offset in range(8):
                    # the depth of the offset walkback here represents how far we ever 
                    # expect the exchanges to be out-of-rabbitMQ-*delivery-time*-sync 
                    # 
                    offsetIdxToCheck = ((self.leadingEdgeBufferIdx - offset) + self.frameBufferSz) % self.frameBufferSz
                    #if offsetIdxToCheck < 0: offsetIdxToCheck = self.frameBufferSz + offsetIdxToCheck# nibble back from end
                    
                    if self.samples[offsetIdxToCheck][exchgSamplesIdx] is None:
                        continue# keep going until you go past the 'oldest' None
                    else:
                        break# ie, stop offsetting once we hit a value-filled (not empty) slot.
                
                
                if offset == 0:# ie, most recent slot/frame/tm has aleady been filled
                    # so, then this *should be the new front
                    #   - advance a frame, store this excahnge's tm as the nominal tmStamp for the frame, and clear slots to be filled
                    #
                    
                    self.globalFrame += 1
                    self.leadingEdgeBufferIdx = self.globalFrame % self.frameBufferSz
                    
                    new_leading_buffIdx = self.leadingEdgeBufferIdx

                    self.frameTms[new_leading_buffIdx] = sampleTm_sec
                    self.samples[new_leading_buffIdx] = [None,]*self.nbExchanges

                    bufferIdxToFill = new_leading_buffIdx

                else:
                    
                    nextAvailNoneSlot =  (offsetIdxToCheck + 1) % self.frameBufferSz# +1 to bring back to the free None slot
                    nextAvailFrameSlotTm = self.frameTms[nextAvailNoneSlot]

                    if math.isclose(nextAvailFrameSlotTm, sampleTm_sec, abs_tol = 0.005):
                        bufferIdxToFill = nextAvailNoneSlot
                    else:
                        pass
                        LOGGER.warning('**----> !! TM SNAPPING: was not able to snap next message on an exchange to the next available tm/frame slot, diff: %s, avail: %s, current: %s, exchange: %s!?', (sampleTm_sec - nextAvailFrameSlotTm), nextAvailFrameSlotTm, sampleTm_sec, exchange_name)
                        # reset...
                        #
                        self.preRecSniff = True
                        self.preRecSniff_stage = 0
                        self.preRecSniff_stageSniffs = 80 
                        self.cur_stageSniffs = 0
                        
            else:
                
                if self.leadingEdgeBufferIdx == exchgStruct['lastFilledIdx']:# ie, most recent slot/frame/tm has aleady been filled
                    # so, then this echange *should represent the new front (freshest/newest seen time)
                    #   - advance a frame, store this excahnge's tm as the nominal tmStamp for the frame (for all exchanges), 
                    #     and clear slots to be filled
                    #
                    
                    self.globalFrame += 1
                    
                    self.leadingEdgeBufferIdx = self.globalFrame % self.frameBufferSz
                    
                    new_leading_buffIdx = self.leadingEdgeBufferIdx

                    self.frameTms[new_leading_buffIdx] = sampleTm_sec
                    # see notes elsewhere on looping buffer overflow, continguous memory
                    #
                    self.frameTms[new_leading_buffIdx + self.frameBufferSz] = self.frameTms[new_leading_buffIdx]
                    
                    bufferIdxToFill = new_leading_buffIdx

                else:

                    nextAvailSlot =  (exchgStruct['lastFilledIdx'] + 1) % self.frameBufferSz
                    nextAvailFrameSlotTm = self.frameTms[nextAvailSlot]

                    if math.isclose(nextAvailFrameSlotTm, sampleTm_sec, abs_tol = 0.005):
                        bufferIdxToFill = nextAvailSlot
                    else:
                        pass
                        LOGGER.warning('**----> !! TM SNAPPING: was not able to time-snap next message on an exchange to the next available frame slot\'s nominal tm, avail: %s, current: %s, exchange: %s!?', nextAvailFrameSlotTm, sampleTm_sec, exchange_name)
                
                exchgStruct['lastFilledIdx'] = bufferIdxToFill
                # exchgStruct['lastFilledIdx'] = self.leadingEdgeBufferIdx
            
            # extract the salient sample data from the ferrying proto buff message...
            #
            if properties.type == 'sjm.pb.ex.EcgData':
                # not surprisingly, ECG exchange data messages don't carry a catheter list member, it just cuts 
                # straight to the channels chase. But we pretend it is structured like the other catheter sample 
                # data, and make it an honoury catheter (see notes in other places too)
                #
                
                gIdx_cathSt = exchgStruct['cath_gIdxSt'][0]# [0] - only 1 'honoury catheter'

                for chanIdx, ecgChan in enumerate(ecgChans):
                    
                    gIdx = (gIdx_cathSt + chanIdx)
                    for tmPntIdx, tmPnt in enumerate(data.data):
                        chanTmPnt = getattr(tmPnt, ecgChan)
                        self.samples[gIdx][bufferIdxToFill][tmPntIdx] = chanTmPnt.value#self.globalFrame
                    
                    # additionally copy sample across into the 'overflow' buffer, so we can do contiguous
                    # memory pulls of subsets of values that run over the looping buffer boundaries 
                    #
                    self.samples[gIdx][bufferIdxToFill + self.frameBufferSz] = self.samples[gIdx][bufferIdxToFill]

            elif properties.type in ('sjm.pb.ex.BioData', 'sjm.pb.ex.LocData'):
                
                isLocData = exchgStruct['isLoc']
                
                for cathIdx, cath in enumerate(tmPnt_0.catheter):# other tmPnts have same cath-chan structure
                    gIdx_cathSt = exchgStruct['cath_gIdxSt'][cathIdx]
                    for chanIdx, chan in enumerate(cath.channel):
                        gIdx = (gIdx_cathSt + chanIdx)
                        for tmPntIdx, tmPnt in enumerate(data.data):# will be just 1, for Loc
                            chanTmPnt = tmPnt.catheter[cathIdx].channel[chanIdx]
                            if isLocData:
                                self.samples[gIdx][bufferIdxToFill][:] = (chanTmPnt.x, chanTmPnt.y, chanTmPnt.z)
                            else:
                                self.samples[gIdx][bufferIdxToFill][tmPntIdx] = chanTmPnt.value#self.globalFrame

                        # copy sample across into the 'overflow' buffer, so we can do contiguous memory pulls of subsets of values 
                        # that run over the looping buffer boundaries 
                        #
                        self.samples[gIdx][bufferIdxToFill + self.frameBufferSz] = self.samples[gIdx][bufferIdxToFill]
        
        if self.dumpMsgFPS:
            msg_curTime = curTime()
            self.msgsRecvd += 1
            self.msg_tmAccum += msg_curTime - self.msg_lastTm
            if self.msg_tmAccum >= 1:
                LOGGER.warning('msgs/sec: %s', self.msgsRecvd)
                self.msgsRecvd = 0
                self.msg_tmAccum -= 1
            self.msg_lastTm = msg_curTime
                            
        # ack is req?
        #
        self.acknowledge_message(basic_deliver.delivery_tag)

    def acknowledge_message(self, delivery_tag):
        """Acknowledge the message delivery from RabbitMQ by sending a
        Basic.Ack RPC method for the delivery tag.
        :param int delivery_tag: The delivery tag from the Basic.Deliver frame
 
        """
        #LOGGER.info('Acknowledging message %s', delivery_tag)
        self._channel.basic_ack(delivery_tag)

    def stop_consuming(self):
        """Tell RabbitMQ that you would like to stop consuming by sending the
        Basic.Cancel RPC command.
 
        """
        if self._channel and self._consuming:
            LOGGER.info('Sending a Basic.Cancel RPC command to RabbitMQ')
            for channel in self._live_export_channels:
                if channel.consumer_tag:
                    cb = functools.partial(
                        self.on_cancelok,
                        userdata = channel.consumer_tag)
                    self._channel.basic_cancel(channel.consumer_tag, cb)

    def on_cancelok(self, _unused_frame, userdata):
        """This method is invoked by pika when RabbitMQ acknowledges the
        cancellation of a consumer. At this point we will close the channel.
        This will invoke the on_channel_closed method once the channel has been
        closed, which will in-turn close the connection.
        :param pika.frame.Method _unused_frame: The Basic.CancelOk frame
        :param str|unicode userdata: Extra user data (consumer tag)
 
        """
        self._consuming = False
        LOGGER.info(
            'RabbitMQ acknowledged the cancellation of the consumer: %s',
            userdata)
        self.close_channel()

    def run(self):# **
        """Run the example code by connecting and then starting the IOLoop.
 
        """
        
        #logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
        
        while not self._stopping:
            
            self._connection = None
            self._deliveries = []
            self._acked = 0
            self._nacked = 0
            self._message_number = 0
            
            try:
                
                self._connection = self.connect()
                
                self._connection.ioloop.start()
                if self.failedCnxn:# **
                    print('\n\n----> failed connection, NOT retrying\n')
                    self.stop()
                    break
                
                
            except KeyboardInterrupt:
                
                self.stop()
                if (self._connection is not None and
                        not self._connection.is_closed):
                    # Finish closing
                    self._connection.ioloop.start()
            
        LOGGER.info('Stopped')

    def stop(self):
        """Stop the example by closing the channel and connection. We
        set a flag here so that we stop scheduling new messages to be
        published. The IOLoop is started because this method is
        invoked by the Try/Catch below when KeyboardInterrupt is caught.
        Starting the IOLoop again will allow the publisher to cleanly
        disconnect from RabbitMQ.
 
        """
        LOGGER.info('Stopping')
        self._stopping = True
        self.stop_consuming()
        self.close_channel()
        self.close_connection()

    def close_channel(self):
        """Invoke this command to close the channel with RabbitMQ by sending
        the Channel.Close RPC command.
 
        """
        if self._channel is not None:
            LOGGER.info('Closing the channel')
            self._channel.close()

    def close_connection(self):
        """This method closes the connection to RabbitMQ."""
        if self._connection is not None:
            if not self._connection.is_closed:
                LOGGER.info('Closing connection')
                self._connection.close()
            else:
                self._connection = None

