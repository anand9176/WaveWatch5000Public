
from __future__ import annotations
from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from waveWatch5000 import WaveWatcher

from WW_GUI_CBs import WW_GUI_CBs
from WW_GUI_elems import WW_GUI_elems

import plotTypeMenus

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import get_backend as MPL_get_backend, ticker
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button, Slider, CheckButtons
import scienceplots# when setting the plt.style.use()

import numpy as np

from typing import Optional
import time

class WW_GUI():
    
    def __init__(self, WWInstance: Optional[WaveWatcher]):
        
        self.WW = WWInstance
        
        self.drawBuffSz = 100# nb of data points to plot (context brings meaning)
        
        self.anim = None
        self.draws = 0
        self.frame = 0#^^!! dangerous/race?: for plotAnim funcAnimation CBs, they pass frame, and is stored here for retrieval
        
        self.lastGraphTime = None
        self.lastDrawnIdx = None
        
        self.nbPlots = 4
        self.plotAlgos = [None,] * self.nbPlots
        
        self.activePlotIdx = -1
        self.activePlotIdx_last = 0
        
        self.plotOpsPosted = False
        self.doAxisAutoScale = None
        self.force_redrawCanvas = False
        
        self.navTrees = [None,] * self.nbPlots
        self.navTreeSelns = [[] for _ in range(self.nbPlots)]
        
        self.curNavDepth = 0
        self.curNavDepthList = [None,] * self.nbPlots
        self.curNavDepthListSelIdx = [0,] * self.nbPlots
        
        self.HUD_bgShadeDownBBox = None
        self.HUD_txts = []
        self.HUD_postTm = -1
        
        self.plotTypeMenus = plotTypeMenus# slightly odd, i realise
        
        self.depressedKeys = set()# nwa, poor Keys
    
    
    def buildGUI(self):
        
        self.guiElems = WW_GUI_elems(self)
        self.guiCBs = WW_GUI_CBs(self)
        
        # ^^!! devTmp (cant seem to do a getattr(self, 'guiElems.tmTicks') ... nested attrib??)
        self.tmTicks = self.guiElems.tmTicks
        
        if 1:# 'attach' the 'numeric keypad ctrlr' to the GUI
            self.guiElems.fig.canvas.mpl_connect(
                'key_press_event',# key_release_event
                self.guiCBs.keypress.keyPress_CB
            )
    
    def setPlotAlgo(self, plotIdx, algoObj):
        
        self.plotAlgos[plotIdx] = algoObj
        self.guiElems.axes_insetLabels[plotIdx].set_text(algoObj.guiName)
    
    def displayGUI(self):
        plt.show()#^^!! matplotlib is taking the __main__ loop at this point !!^^
    
    def shadeActivePlot(self):
        
        for idx, ax in enumerate(self.guiElems.axes):
            
            if idx == self.activePlotIdx:
                ax.set_facecolor('lightgreen')
            else:
                ax.set_facecolor('None')
        
        self.guiElems.fig.canvas.flush_events()
        self.guiElems.fig.canvas.draw()
    
    def postPlotOpts(self):
        
        if self.curNavDepth == 0:# plot seln, no opts listing
            
            # clear out the HUD for any prev plot ops posted
            #
            if self.plotOpsPosted:
                self.setHUD([])
                self.plotOpsPosted = False
            
        else:
            
            self.setHUD(self.curNavDepthList[self.activePlotIdx])
            
            self.plotOpsPosted = True
        
        # force redraw
        #
        self.guiElems.fig.canvas.flush_events()
        self.guiElems.fig.canvas.draw()
    
    def setHUD(self, texts, tm = 2.0):
        
        # kill any existing...
        #
        if self.HUD_bgShadeDownBBox is not None:
            self.HUD_bgShadeDownBBox.remove()
            del(self.HUD_bgShadeDownBBox)
            self.HUD_bgShadeDownBBox = None
        if self.HUD_txts:
            for HUD_txt in self.HUD_txts:
                HUD_txt.remove()
                del(HUD_txt)
            self.HUD_txts = []
        
        if texts:
            
            #fig_width, fig_height = self.guiElems.fig.get_size_inches()
            
            self.HUD_bgShadeDownBBox = mpl.patches.FancyBboxPatch(
                (0, 0), 
                1, 1,#^^ cant figure extents of this box o_O
                boxstyle = 'square',#round, pad=10',#'square',
                #edgecolor = 'black',
                color = 'slateblue',
                alpha = 0.8
            )
            self.guiElems.fig.add_artist(self.HUD_bgShadeDownBBox)
        
            
            nbTexts = len(texts)
            vertSepSz = 1./nbTexts
            for idx, txt in enumerate(texts):
                
                self.HUD_txts.append(
                    self.guiElems.fig.text(
                        0.5, (((nbTexts - idx) * vertSepSz) - (vertSepSz * 0.5)),
                        txt, 
                        ha = 'center', va = 'center', 
                        fontsize = 40, alpha = 1.0,
                        bbox = dict(
                            facecolor = (
                                'seagreen' if (idx == self.curNavDepthListSelIdx[self.activePlotIdx])
                                else 'gold'
                            ), 
                            alpha = 0.4, 
                            boxstyle = 'round'
                        ),
                    )
                )
            
            #self.HUD_postTm = time.time()
    
    def setGraphCB(self):
        
        CB = self.guiCBs.plotAnim.updateGraph
        
        self.anim = FuncAnimation(#^^!! this is called immediately
            self.guiElems.fig,
            CB, 
            interval = 50,
            blit = True,# draw fast, just update the line 'artist(s)' (and curvVal txt)
            cache_frame_data = False
        )
        print('hitched up funcAnim CB')
    
    def remGraphCB(self):
        
        if self.anim:
            self.anim.event_source.stop()
        self.anim = None
        print('removed funcAnim CB')
    