# MAKE THIS CNXN-TYPE AGNOSTIC (this is EnSite centric ATM [just components of the the liveMonitor() left to generalise])
#

from __future__ import annotations
from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from waveWatch5000 import WaveWatcher

import cnxns

from importlib import import_module

import time

from pprint import pprint as pp

class WW_cnxn():
    
    def __init__(self,
            WWInstance: Optional[WaveWatcher],
            cnxnType,
            **kwargs# frameBufferSz
        ):
        
        self.WW = WWInstance
        
        self.dataStream = None
        self.cnxnEstablished = False
        
        self.cnx(cnxnType, **kwargs)
    
    def cnx(self,
            cnxnType,
            **kwargs
        ):
        
        # add in some extra kwargs beyond what the Cnxn-user/client supplies...
        #
        kwargs['wW_cnxnEstablishedCB'] = self.cnxnEstablishedCB# the ./cnxns/type/dataStreamer.py will handle/pass-on calling of this once the cnxn is established
        
        cnxnMod = import_module(
            ('cnxns.' +cnxnType+ '.dataStreamer')
        )
        
        self.dataStream = cnxnMod.Stream(**kwargs)# aka clientThread
        self.dataStream.start()# kick off connecting to the stream source/server
        
        # wait for stream cnxn to be established
        #
        tmOut = 10.
        tmStart = time.time()
        while not self.cnxnEstablished and (tmStart - time.time()) < tmOut:
            time.sleep(0.1)
        
        if not self.cnxnEstablished:
            raise Exception('Data stream connection (to: ' +cnxnType+ ') failed to establish after ' +str(tmOut)+ ' sec timeout.')
        else:# cnxn made, primed ready to liveMonitor the stream now
            
            # add in any cnxn-specific menu items
            #
            if hasattr(self.WW, 'GUI'):
                self.dataStream.popCnxnDynPropMenu(
                    self.WW.GUI.plotTypeMenus
                )
    
    def cnxnEstablishedCB(self):
        print('--> cnxnEstablished CB, as called from rabbitMQ client\'s .on_connection_open()')
        self.cnxnEstablished = True
    
    def deCnx(self):
        try:
            if self.dataStream is not None:
                self.dataStream.close()
            del(self.dataStream)
            self.dataStream = None
        except:
            print('some issue closing the existing client connection...')
            raise
    
    def liveMonitor(self):
        
        DWSRabMQClient = self.dataStream.client# still EnSite-centric
        
        # wait for sniffing, and a bit of sample accumulation to complete
        #
        while (
            DWSRabMQClient is None or
            len(DWSRabMQClient.samples) < 1 or 
            DWSRabMQClient.leadingEdgeBufferIdx == -1 or
            DWSRabMQClient.leadingEdgeBufferIdx - self.WW.bitBack - self.WW.processBufferFrameSz < 0
        ):
            print('waiting for client to have collected some samples...')
            time.sleep(0.8)
        
        #print('chans by index:');(DWSRabMQClient.chans_byIdx)
        
        if 0:
            targCathics = [cath for cath in DWSRabMQClient.samples_struct[self.WW.LOC_exchg]['caths'] if cath[0] == self.WW.targCath]
            if not len(targCathics):
                raise Exception('----> cant find targCath in the dataStream:', self.WW.targCath)
        
        # ATOW, the samples_struct is considered fixed (because we arent re-sniffing the data stream for changes [eg catheters unplugged, channels renamed], ATOW)
        #   > 
        #
        
        
        if not self.WW.headless:
            
            if self.WW.GUI.anim is None:
                
                devAlgoLst = [('genericAlgo_' +str(plotIdx)) for plotIdx in range(self.WW.GUI.nbPlots)]
                devAlgoLst[0] = 'dominantFrequency'
                # ^^!! devTmp setup
                # set each slotAlgo to a same-indexed generic algo,
                # and align plotAlgos to the same ones
                #
                for plotIdx, algoName in enumerate(devAlgoLst):
                    
                    if algoName is None: continue
                    
                    self.WW.setSlotAlgo(
                        plotIdx,
                        algoName
                    )
                    
                    self.WW.GUI.setPlotAlgo(plotIdx, self.WW.slotAlgos[plotIdx])
                    #self.WW.GUI.plotAlgos[plotIdx] = self.WW.slotAlgos[plotIdx]
                
                self.WW.GUI.setGraphCB()# ^^!! ATM, this is setting the maximum output freq
                
            else:
                
                self.WW.GUI.anim.resume()
    
    def haltMonitoring(self):
        
        if self.WW.GUI.anim is not None:
            self.WW.GUI.anim.pause()

