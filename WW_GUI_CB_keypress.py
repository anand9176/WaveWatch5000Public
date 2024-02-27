from __future__ import annotations
from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from WW_GUI import WW_GUI

import copy

numbs_str = [str(_) for _ in range(10)]

class WW_GUI_CB_keypress():
    
    def __init__(self, WWGUIInstance: WW_GUI):
        
        self.WWGUI = WWGUIInstance
        #self.WW = self.WWGUI.WW
    
    def keyPress_CB(self, event):
        
        #self.depressedKeys.add(event.key)# removed on keyRelease_CB()
        #print(f"Key '{event.key}' pressed")
        
        try:
            pressedNumb = int(numbs_str.index(event.key))
        except ValueError:# not a number (no index)
            return
        
        up   = (pressedNumb == 8)
        down = (pressedNumb == 2) or (pressedNumb == 5)
        back = (pressedNumb == 4)
        dive = (pressedNumb == 6)
        zero = (pressedNumb == 0)
        
        
        '''
            self.processBufferSzMult -= 0.1
            self.processBufferSzMult = max(self.processBufferSzMult, 0.1)
            self.winSzTxt.set_text(
                ('winSz: ' +str(self.processBufferSzMult))
            )
            self.WWGUI.force_redrawCanvas = True
        '''
        
        navDepthChg = False
        
        if self.WWGUI.curNavDepth == 0:# plot seln
            
            if zero and (self.WWGUI.activePlotIdx != -1):# a plot is selected, and you hit zero to autofit it
                self.WWGUI.doAxisAutoScale = self.WWGUI.activePlotIdx
                back = True#^^ nav back out!
            
            if (up or down) and (self.WWGUI.activePlotIdx != -1):
                self.WWGUI.activePlotIdx += ((-1 if up else 1) + self.WWGUI.nbPlots)
                self.WWGUI.activePlotIdx %= self.WWGUI.nbPlots
            elif back:
                if self.WWGUI.activePlotIdx != -1:
                    self.WWGUI.activePlotIdx_last = self.WWGUI.activePlotIdx
                self.WWGUI.activePlotIdx = -1# no plot selected/hilighted
            elif dive:
                if self.WWGUI.activePlotIdx == -1:
                    self.WWGUI.activePlotIdx = self.WWGUI.activePlotIdx_last
                else:
                    self.WWGUI.curNavDepth = 1
                    navDepthChg = True
            
            if self.WWGUI.anim:
                if self.WWGUI.activePlotIdx == -1:
                    self.WWGUI.anim.resume()
                else:
                    self.WWGUI.anim.pause()
            
            #if self.WWGUI.curNavDepth != 1 and self.WWGUI.activePlotIdx != -1:# dont need to shade if diving down, or backing out
            self.WWGUI.shadeActivePlot()
            
        elif self.WWGUI.curNavDepth >= 1:# you are making menu slections, dives, at some depth
            
            actPltIdx = self.WWGUI.activePlotIdx
            
            if up or down:
                
                nbNavListItems = len(self.WWGUI.curNavDepthList[actPltIdx])
                curSelIdx = self.WWGUI.curNavDepthListSelIdx[actPltIdx]
                if nbNavListItems:
                    curSelIdx += ((-1 if up else 1) + nbNavListItems)
                    curSelIdx %= nbNavListItems
                else:
                    curSelIdx = 0
                
                self.WWGUI.curNavDepthListSelIdx[actPltIdx] = curSelIdx
                
                # store selected item (as name/navTrees-dict-key) for the cur nav depth
                #
                self.WWGUI.navTreeSelns[actPltIdx][(self.WWGUI.curNavDepth - 1)] = self.WWGUI.curNavDepthList[actPltIdx][curSelIdx]
                
                print('navTreeSelns:', ''.join(['x' if sel is None else sel for sel in self.WWGUI.navTreeSelns[actPltIdx]]))
                
            elif back or dive:
                
                self.WWGUI.curNavDepth += (-1 if back else 1)
                
                if back:
                    ...#self.WWGUI.navTreeSelns[self.WWGUI.activePlotIdx][self.WWGUI.curNavDepth + 1] = None
                
                navDepthChg = True
        
        if navDepthChg:
            # populate the current navigation depth's list of items
            #   > self.WWGUI.curNavDepthList[actPltIdx]
            #
            
            actPltIdx = self.WWGUI.activePlotIdx
            
            if len(self.WWGUI.navTreeSelns[actPltIdx]) < self.WWGUI.curNavDepth:
                self.WWGUI.navTreeSelns[actPltIdx].append(None)# expand as we explore
            
            # populate an algo's GUI elems on-demand
            #
            if self.WWGUI.plotAlgos[actPltIdx].guiMenu is None:
                self.WWGUI.plotAlgos[actPltIdx].guiMenu = copy.deepcopy(
                    self.WWGUI.plotTypeMenus.menus[
                        self.WWGUI.plotAlgos[actPltIdx].plotType
                    ]
                )
            
            #self.navTrees[actPltIdx] = 
            
            navDepthList = self.WWGUI.plotAlgos[actPltIdx].guiMenu#self.navTrees[actPltIdx]
            #print('navDepthList, root:', navDepthList)
            
            for selnDepth, navTreeSeln in enumerate(self.WWGUI.navTreeSelns[actPltIdx]):
                print('navDepth, selnDepth', selnDepth, navTreeSeln)
                #if navTreeSeln is None:                    navTreeSeln = navDepthList
                
                if (selnDepth + 1) >= self.WWGUI.curNavDepth: break# don't look at 'stale' navigation at lower depths. +1 as a selnDepth is one ahead of the nav depth (once youve selected, THEN you dive)
                
                
                if navTreeSeln is None:# first time hitting this depth, select first item (is ordered dict)
                    curDepthKeys = list(navDepthList.keys())
                    if curDepthKeys:
                        navTreeSeln = curDepthKeys[0]
                    else:
                        break# no items at this depth (you are on a leaf), so stop looking deeper
                
                navDepthList = navDepthList[navTreeSeln]
            
            self.WWGUI.curNavDepthList[actPltIdx] = list(navDepthList.keys())
            
            print('curNavDepthList:', self.WWGUI.curNavDepthList[actPltIdx])
        
        
        # there was some GUI interaction, update the GUI (inc kill, if backing out)
        #
        self.WWGUI.postPlotOpts()
    
    def keyRelease_CB(self, event):
        if event.key in self.depressedKeys:
            self.depressedKeys.remove(event.key)
        print(f"Key '{event.key}' released")
