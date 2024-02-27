'''
Please see licensing information in file 'Software Licence Terms _ Flinders University _Wavewatch5000.pdf'
This applies to all source files within this reository unless otherwise noted.
'''


from imports import *

class WaveWatcher():
    
    def __init__(self):
        
        self.headless = False#^^!! should read ctx for potential headless mode, and sub in a dummy WW_GUI for total sev
        if not self.headless:
            self.GUI = WW_GUI(self)
        
        self.cnxn = None
        
        self.frameBufferSz = 600# in 100Hz frames (how much we store in live rolling memory buffer)
        self.processBufferSzMult = 2.0# essentially seconds of data to process
        self.processBufferSz = self.processBufferSzMult*2000# in samples (eg 4000Hz = ~2sec, at the sampling rate of 2000Hz)
        assert(self.processBufferSz % 20 == 0)# processBufferSz must be a multiple of 20 (the 100Hz sub-sample sz)
        self.processBufferFrameSz = int(self.processBufferSz / 20)
        
        self.bitBack = 50# from the sample buffer's current write head front
        self.NonCLChanToProc = 0
        
        # insert name that Abbott EnSite rep calls the HDG cath...
        #
        self.targCath = 'HDG-Advisor HD Grid SE'#3-Advisor HD Grid SE'# 1-Advisor HD Grid SE
        
        self.uniPolar = True
        self.LOC_exchg = 'EX.LOC' if self.uniPolar else 'EX.BIP_LOC'
        self.electro_exchg = 'EX.UNI_FLT' if self.uniPolar else 'EX.BIP_FLT'
        
        if 0: self.calcTmPnts = [0.,]*self.drawBuffSz
        
        self.nbAlgos = 4
        self.slotAlgos = [None,] * self.nbAlgos
        
        self.boot()
    
    def boot(self):
        
        try:
            
            if not self.headless:
                self.GUI.buildGUI()
            
            self.cnxn = WW_cnxn(# waits a certain timeout length to make cnxn
                self,
                'EnSite',
                **{'frameBufferSz' : self.frameBufferSz},
            )
            
            try:
                self.cnxn.liveMonitor()
            except KeyboardInterrupt:
                raise Exception('aborted liveMonitoring of cnxn (via KeyboardInterrupt)')
            
            
            if not self.headless:
                try:
                    self.GUI.displayGUI()#^^!! matplotlib will take the main loop at this point
                except:
                    self.cnxn.deCnx()
                    raise
            #else: ...what is our headless loop?
            
            # mpl window escaped/excepted (show is over)...
            #
            if self.cnxn:
                self.cnxn.deCnx()
            
        except:
            raise
        finally:
            # close the cnxn
            #
            if self.cnxn:
                self.cnxn.deCnx()
    
    def getAlgos(self):
        
        # pp(algoObjs)
        
        for algoName, algo in algoObjs.items():
            if 0:
                pp(
                    algo.compute(
                        (algoName, algoName)
                    )
                )
            #pp(algo.guiName_short)
    
    def setSlotAlgo(self, slotIdx, algo):
        #print('setSlotAlgo', slotIdx, algo)
        self.slotAlgos[slotIdx] = algoObjs[algo]


# > run client from the cmd line, _Py3_ (/venv), using matplotlib as GUI
#
if __name__ == '__main__':
    
    try:
        wW = WaveWatcher()
    except:
        raise
    finally:
        # close out cnxns if they exist
        #
        if hasattr(locals(), 'wW') :
            if hasattr(wW, 'cnxn'):
                wW.cnxn.deCnx()
            del(wW)
        print('out')
