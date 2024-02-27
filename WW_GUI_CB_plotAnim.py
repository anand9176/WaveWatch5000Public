from __future__ import annotations
from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from WW_GUI import WW_GUI

import exceptions

import time

class WW_GUI_CB_plotAnim():
    
    def __init__(self, WWGUIInstance: WW_GUI):
        
        self.WWGUI = WWGUIInstance
        self.WW = self.WWGUI.WW
        
        self.plotCalcs = [[0.3,]*self.WWGUI.drawBuffSz for _ in range(self.WWGUI.nbPlots)]# just init values, 0.3 to be a bit off 0-1 centre for a visual reason
    
    def updateGraph(self, frame):
        
        # disable redraw of graph if GUI menu is posted
        #
        if self.WWGUI.activePlotIdx != -1: return []
        
        self.WWGUI.draws += 1
        
        if 0:
            if self.lastGraphTime == None: self.lastGraphTime = time.time()
            print('tm:', time.time() - self.lastGraphTime)
            self.lastGraphTime = time.time()
        
        self.WWGUI.frame = frame# ^^!! dev tmp: so getattr() so algo input requests can get at it
        
        
        if hasattr(self.WW, 'cnxn') and self.WW.cnxn is not None:# EnSite data prep (need to push off to EnSite area)
            
            rabMQClient = self.WW.cnxn.dataStream.client
            
            if rabMQClient is None: return ()
            
            bitBackFromLeadingEdge_buffIdx = (
                (rabMQClient.leadingEdgeBufferIdx - self.WW.bitBack) + self.WW.frameBufferSz
            ) % self.WW.frameBufferSz
            
            if self.WWGUI.lastDrawnIdx == bitBackFromLeadingEdge_buffIdx: return ()
            self.WWGUI.lastDrawnIdx = bitBackFromLeadingEdge_buffIdx
            
            sampleSlotsToProcess_stIdx = (bitBackFromLeadingEdge_buffIdx - self.WW.processBufferFrameSz)
            sampleSlotsToProcess_endIdx = bitBackFromLeadingEdge_buffIdx
            if sampleSlotsToProcess_stIdx < 0:# see if we cross the buffer boundary, and if so go into the buffer wrapper double up (contiguosu memory, so we get 'views', not copies)
                sampleSlotsToProcess_stIdx += self.WW.frameBufferSz
                sampleSlotsToProcess_endIdx += self.WW.frameBufferSz
            
            #print(sampleSlotsToProcess_stIdx, sampleSlotsToProcess_endIdx)
            
            
            # ^^!! this business below to get the appropriate chan_gIdxs could/should 
            # be done just once, when setting the targetCath, and then cached
            #
            
            samples_struct = rabMQClient.samples_struct
            samples = rabMQClient.samples
            chans_gIdxLUp = rabMQClient.chans_gIdxLUp
            
            #chanNames = [cath for cath in samples_struct[self.LOC_exchg]['caths'] if cath[0] == self.targCath][0][1]
            #chanNames = chanNames[:-2]# trim off the S chans
            
            targCath = [cath for cath in samples_struct[self.WW.LOC_exchg]['caths'] if cath[0] == self.WW.targCath]
            if not targCath:
                chanNames = []
                print('--> !! taget catheter not present !! :', self.WW.targCath)
            else:
                chanNames = targCath[0][1]# chan == electrode
                if self.WW.uniPolar:#^^!! only other that we look at is bipolar on HD Grid, which has no shaft electrodes to exclude...
                    chanNames = chanNames[:-2]# trim off the S chans
            
            nbElecs = len(chanNames)
            
            self.electroData = [None,]*nbElecs
            for electroIdx, chanName in enumerate(chanNames):# LOC_chans names shoudl be same between the EX.UNI and self.LOC_Exchg exchgs
                chan_gIdx = chans_gIdxLUp[
                    (self.WW.electro_exchg, self.WW.targCath, chanName)
                ]
                # reshape(-1) to flatten out the 20 sub samples...
                #   ^^!! does this break np memory 'view'? A copy?
                #
                self.electroData[electroIdx] = samples[chan_gIdx][sampleSlotsToProcess_stIdx : sampleSlotsToProcess_endIdx].reshape(-1)
            
            self.electroLocs = [None,]*nbElecs
            for electroIdx, chanName in enumerate(chanNames):
                chan_gIdx = chans_gIdxLUp[
                    (self.WW.LOC_exchg, self.WW.targCath, chanName)
                ]
                self.electroLocs[electroIdx] = samples[chan_gIdx][sampleSlotsToProcess_stIdx : sampleSlotsToProcess_endIdx]
        
        if 0:# resolving X value (in the end, time point needs to be the time that the rcessed window ends on
            
            cTm = curTime()
            self.calcTmPnts[:-1] = self.calcTmPnts[1:]
            self.calcTmPnts[-1] = cTm
            
            tmPntsAgo = [(cTm - calcTm) for calcTm in self.calcTmPnts]
            #tmPntsAgo.reverse()
            tmPntsAgo = self.WWGUI.tmTicks# so it isnt fluxing, and maxing things slow(but, its FALSE)
        
        # compute graph plot algos here (in serrial, for now)
        #   --> so compute is at the pace of the funcAnimation callback rate
        #
        # ^^!!  need to have a .preCaclCache() on algoObjs too
        #   >> and we need to dirty it when we twiggle parms, etc
        #
        redrawables = []# for funcAnimation to handle
        for idx, plotAlgo in enumerate(self.WWGUI.plotAlgos):
            
            if plotAlgo is None: continue
            #print(plotAlgo.guiName)
            if 0:
                if not(plotAlgo.doneVarBinds):
                    plotAlgo.doneVarBinds = True
            
            compInputRequests = plotAlgo.inputs
            compInputs = [None,]* len(compInputRequests)
            for inputIdx, compInput in enumerate(compInputRequests):
                
                dataHolder, dataAttr = compInput
                
                if dataHolder == 'cnxn':
                    dataObj = self.WW.cnx
                elif dataHolder == 'WW':
                    dataObj = self.WW
                elif dataHolder == 'WWGUI':
                    dataObj = self.WWGUI
                else:
                    dataObj = self
                
                compInputs[inputIdx] = getattr(dataObj, dataAttr)
            
            # DO the compute
            #
            hasSecondaryResult = False
            try:
                computedResult = plotAlgo.compute(compInputs)
                if type(computedResult) == tuple:
                    print('----->', computedResult)
                    computedResult, computedResult_2 = computedResult[:2]
                    hasSecondaryResult = True
            except exceptions.NoElectrodes:
                computedResult = -1.0
            except:
                try:
                    self.WW.cnx.deCnx()
                except:
                    pass
                raise
            
            # shift the calcs down one, and add latest to the end
            #
            #   ^^!! timing between calc indexes is not necessarily uniform !!^^
            #       > is driven by matplotlib funAnimn callback rate
            #       > can be paused due to GUI, or slowed by other algos, ETC!!
            #       > !!!!!! WARNED !!!!!!
            #
            self.plotCalcs[idx][:-1] = self.plotCalcs[idx][1:]
            self.plotCalcs[idx][-1] = computedResult
            
            line = self.WWGUI.guiElems.axes_lines[idx]
            line.set_data(
                self.WWGUI.tmTicks,
                self.plotCalcs[idx]
            )
            redrawables.append(line)
            
            curValTxt = self.WWGUI.guiElems.axes_curValTxt[idx]
            computedResult_abs = abs(computedResult)
            if computedResult_abs < 0.01 or computedResult_abs >= 1e6:
                computedResult_str = f'{computedResult:.1e}'
            else:
                computedResult_str = f'{computedResult:.1f}'
            curValTxt.set_text(computedResult_str)
            redrawables.append(curValTxt)
            
            if hasSecondaryResult:
                curValTxt_2 = self.WWGUI.guiElems.axes_curValTxt_2[idx]
                computedResult_2_abs = abs(computedResult_2)
                if computedResult_2_abs < 0.01 or computedResult_2_abs >= 1e6:
                    computedResult_2_str = f'{computedResult_2:.1e}'
                else:
                    computedResult_2_str = f'{computedResult_2:.1f}'
                curValTxt_2.set_text(computedResult_2_str)
                redrawables.append(curValTxt_2)
            
        
        
        redrawCanvas = False
        if self.WWGUI.HUD_postTm != -1:
            ...# jesus!
            #redrawCanvas = True
        
        #if 0 and self.WWGUI.doAxisAutoScale:
        #if 1 and self.WWGUI.draws % 20 == 0:
        if self.WWGUI.doAxisAutoScale is not None:
            
            axToAutoFit = self.WWGUI.guiElems.axes[self.WWGUI.doAxisAutoScale]
            for ax in (axToAutoFit,):# left as an iterable
                ax.relim()# first!
                ax.autoscale_view(True, True)
            
            redrawCanvas = True
            self.WWGUI.doAxisAutoScale = None
        
        if redrawCanvas or self.WWGUI.force_redrawCanvas:# force a redraw now for the non-blit stuff
            self.WWGUI.guiElems.fig.canvas.flush_events()
            self.WWGUI.guiElems.fig.canvas.draw()
            #plt.pause(0.001)
            
            self.WWGUI.force_redrawCanvas = False
        
        return redrawables# this is for the funcAnimation