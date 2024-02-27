from __future__ import annotations
from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from WW_GUI import WW_GUI

#from WW_GUI import WW_GUI

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import get_backend as MPL_get_backend, ticker
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button, Slider, CheckButtons
import scienceplots# when setting the plt.style.use()

import numpy as np

class WW_GUI_elems():
    
    def __init__(self, WWGUIInstance: WW_GUI):
        
        self.WWGUI = WWGUIInstance
        self.WW = self.WWGUI.WW
        
        self.nbPlots = 4
        
        self.fig = None
        self.axes = None
        self.axes_lines = []
        self.axes_insetLabels = []
        self.axes_curValTxt = []
        self.axes_curValTxt_2 = []
        
        self.tmTicks = None
        
        self.buildGUIElems()
    
    def buildGUIElems(self):
        
        try:
            
            #print(MPL_get_backend())
            #assert(MPL_get_backend() in ('TkAgg', 'QtAgg'))
            
            plt.style.use(['science','notebook', 'grid'])# scienceplots mod
            plt.rcParams['toolbar'] = 'None'
            
            #self.tmTicks = np.linspace(0, self.WWGUI.drawBuffSz, self.WWGUI.drawBuffSz)
            self.tmTicks = np.linspace(6, 0, self.WWGUI.drawBuffSz)# $$
            
            self.fig, self.axes = plt.subplots(
                nrows = self.nbPlots, ncols = 1,
                figsize = (12, 4),
                #gridspec_kw = {'height_ratios': [2, 1, 1]}
                sharex = True
            )
            #(self.ax_CL, self.ax_Di, self.ax_ShEn, self.ax_DF) = self.axes# dev!! for now
            #axes = (self.ax_CL, self.ax_Di, self.ax_ShEn, self.ax_DF)
            
            self.fig.suptitle('waveWatch5000')
            
            def _milliseconds_formatter(x, pos):
                milliseconds = int(x * 40)
                seconds = milliseconds // 1000
                milliseconds %= 1000
                return f'{seconds:02d}:{milliseconds:03d}'
            def milliseconds_formatter(x, pos):
                return f'{x:.02f}'
            
            # because sharex = True, set gear on last ax
            self.axes[-1].xaxis.set_major_formatter(
                ticker.FuncFormatter(milliseconds_formatter)
            )
            self.axes[-1].set_xlabel('seconds ago')# on last axis
            self.axes[-1].invert_xaxis()
            
            dummyCols = ('red', 'green', 'purple', 'blue')
            dummyNames = ('CL', 'Di', 'ShEn', 'DF')
            
            self.axes_lines = [None,]*len(self.axes)
            self.axes_insetLabels = [None,]*len(self.axes)
            self.axes_curValTxt = [None,]*len(self.axes)
            self.axes_curValTxt_2 = [None,]*len(self.axes)
            for axIdx, ax in enumerate(self.axes):
                
                y = np.sin(self.tmTicks + axIdx*0.7) + 0.3*np.random.randn(self.WWGUI.drawBuffSz)
                
                self.axes_lines[axIdx], = ax.plot(
                    self.tmTicks, y, 
                    '-', color = dummyCols[axIdx], lw = 2, ms = 3
                )
                
                self.axes_insetLabels[axIdx] = ax.text(
                    0.01, 0.1, 
                    (dummyCols[axIdx]+ 'Alg'), 
                    #dummyNames[axIdx],
                    transform = ax.transAxes,
                    fontsize = 20, fontweight = 'heavy',
                    bbox = dict(facecolor = dummyCols[axIdx], alpha = 0.3)
                )
                #ax.set_ylim(0, 15)
                
                self.axes_curValTxt[axIdx] = ax.text(
                    0.84, 0.1,#-0.15, 1.,
                    '',#('winSz: ' +str(self.WW.processBufferSzMult)), 
                    transform = ax.transAxes,
                    fontsize = 25, fontweight = 'heavy',
                    #bbox = dict(facecolor = 'green', alpha = 0.2)
                )
                
                if True:
                    self.axes_curValTxt_2[axIdx] = ax.text(
                        0.95, .8,#-0.15, 1.,
                        '',#('winSz: ' +str(self.WW.processBufferSzMult)), 
                        transform = ax.transAxes,
                        fontsize = 15, fontweight = 'heavy',
                        #bbox = dict(facecolor = 'green', alpha = 0.2)
                    )

            
            #self.line_CL, self.line_Di, self.line_ShEn, self.line_DF = self.axes_lines# ^^!! tmp dev
            
            if 0:
                
                self.winSzTxt = self.axes[0].text(
                    -0.15, 1.,
                    ('winSz: ' +str(self.WW.processBufferSzMult)), 
                    transform = self.axes[0].transAxes,
                    fontsize = 10, fontweight = 'heavy',
                    bbox = dict(facecolor = 'green', alpha = 0.3)
                )
            
            #axes.set_xlabel('Time [s]')
            #axes.set_ylabel(r'$\frac{d}{dx} f(x)$', fontsize=15)
            
            
        except:
            raise
        finally:
            ...
    