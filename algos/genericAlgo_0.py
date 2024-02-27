

import exceptions

import numpy as np
import scipy
# other imports requried by your algorithms (may need to 'pip install' them to the local venv)

genAlgoIdx = int(__file__[-4])

thisAlgoProps = {# dont rename this
    'guiName' : ('genAlgo_' +str(genAlgoIdx)),
    'guiName_short' : ('GA#'+str(genAlgoIdx)),
    'guiColor' : 'tomato',# see /algos/namedColours_matplotlib.webpp for list of colors and their names
    'plotType' : 'basicLineMenu',
    'inputs' : (
        #('cnxn', 'curWin'),
        ('', 'electroData'),
        #('', 'electroLocs'),
        ('WWGUI', 'frame'),
        ('WWGUI', 'tmTicks'),
    ),
}


def compute(data):
    
    if 0:# toy
        frame, tmTicks = data
        res = np.sin(tmTicks + genAlgoIdx*1.15 + (frame * 0.6)) + 0.1*np.random.randn(len(tmTicks))
        res = res[0]
        #res = np.sin(genAlgoIdx*1.15 + (frame * 0.6)) + 0.1*np.random.randn(1)
        #print(len(res))
    else:
        frame, tmTicks, electroData = data
        res = electroData[genAlgoIdx*2][0]
        #print(res)
    
    result = res
    return result
