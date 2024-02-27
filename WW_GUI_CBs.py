from __future__ import annotations
from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from WW_GUI import WW_GUI
from WW_GUI_CB_keypress import WW_GUI_CB_keypress
from WW_GUI_CB_plotAnim import WW_GUI_CB_plotAnim

class WW_GUI_CBs():
    
    def __init__(self, WWGUIInstance: Optional[WW_GUI]):
        
        self.WWGUI = WWGUIInstance
        #self.WW = self.WWGUI.WW
        
        self.keypress = WW_GUI_CB_keypress(self.WWGUI)
        self.plotAnim = WW_GUI_CB_plotAnim(self.WWGUI)

