# Starting template for your own 
#
# Copy-paste (or save-as) this into a new file, yourAlgoName.py,
# in this same /algos folder, fill in appropriate algo props below, 
# and write your custom compute algorithm code into the compute() 
# function below.
#

import exceptions

import numpy as np
import scipy
# other imports requried by your algorithms (may need to 'pip install' them to the local venv)

thisAlgoProps = {# dont rename this
    'guiName' : 'UniqueAlgoName',
    'guiName_short' : 'UFAO',
    'guiColor' : 'tomato',# see /algos/namedColours_matplotlib.webpp for list of colors and their names
}

def compute(data):# dont rename this
    
    print('Compute', data)
    
    # Compute
    #   > custom algorithm logic goes here
    #
    result = 4.6692016091029909# could also be an array

    return result
