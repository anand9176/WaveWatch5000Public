'''

EnSiteX data streamer thread
> a wrapper around the EnSite LiveExportAsyncClient (a rabbitMQ client to the DWS)

'''

from . import connectionDetails

from . import LiveExportAsyncClient

import threading, time
from time import time as curTime

class Stream(threading.Thread):# aka Rabbit Client handling thread, here, for EnSite
    
    def __init__(self,
            **kwargs
        ):
        
        self.client = None
        
        self.frameBufferSz = kwargs.get('frameBufferSz', None)# frames == packets, that arrive at 100Hz (w electro carrying 20 sub samples)
        self.cnxnEstablishedCB = kwargs.get('wW_cnxnEstablishedCB', None)
        
        # FPS initial
        self.inter = 0
        self.fps = 0
        self.start_time = curTime()
        
        threading.Thread.__init__(self)
    
    def run(self):
        
        self.client = LiveExportAsyncClient.LiveExportAsyncClient(
            dumpPath = connectionDetails.dumpPath,
            bus_host = connectionDetails.address,
            bus_port = connectionDetails.ampqPort,
            exchangesToSubscribeTo = connectionDetails.exchgSubs,
            external_onCnxnCB = self.cnxnEstablishedCB,
            frameBufferSz = self.frameBufferSz,
            privateKeyPass = connectionDetails.privateKeyPass or False 
        )
        
        try:
            self.client.run()# blocking, until client stopped/failed...
        except:
            raise
        finally:
            #print('....shouldnt see this until the client connection has finished running/closed, or failed...')
            self.client = None
            print('data streamer done')
    
    def close(self):
        if self.client is None:
            print('apparently no EnSite LiveExport client was created, to be able to close it.')
        else:
            self.client.stop()
    
    def popCnxnDynPropMenu(self, plotTypeMenus):
        
        plotTypeMenus.basicLineMenu['algo parms']['global']['cnxnSpecOpt'] = 'EnSiteX'
    
    def msgCB(self, tmPnt, extraMsg = None):
        
        if extraMsg:
            print('msgCB!!', tmPnt, extraMsg)
        
        # fps performance print
        #
        end_time = curTime()
        self.fps += 1
        self.inter += end_time - self.start_time
        if self.inter >= 1:
            print('FPS:', self.fps)
            self.fps = 0
            self.inter -= 1
        self.start_time = end_time

