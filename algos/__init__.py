# this imports all algos/modules in this folder, 
# and makes them available in the algoObjs dict
#

from . import algoFactory
from . import algoSpecCheck


import glob
import os

thisFileDir = os.path.dirname(__file__)
module_files = glob.glob(os.path.join(thisFileDir, "*.py"))

specialModules = ('__init__', 'algoFactory', 'algoTemplate', 'algoSpecCheck')

# dyn import modules...
#
algoObjs = {}
for module_file in module_files:
    
    module_name = os.path.basename(module_file)[:-3]  # Remove the ".py" extension
    
    if module_name in specialModules: continue# skip special modules
    if module_name.startswith('_'): continue# temp skip of algos
    
    # import the module script (has a dict of props, a compute() function, maybe a few others)
    #
    mod = __import__(module_name, globals(), locals(), [], 1)
    
    # check that the athored algo module meets some spec reqs
    #
    algoSpecCheck.inspect(mod)
    
    # make an Algo object, attaching the algo-module-script functions, etc
    #
    algo = algoFactory.Algo(mod.thisAlgoProps)
    algo.doneVarBinds = False
    algo.compute = mod.compute
    
    algo.has_preCompute = hasattr(mod, 'preCompute')
    if algo.has_preCompute:
        algo.preCompute = mod.preCompute
    algo.has_preCalcs = hasattr(mod, 'preCalcs')
    if algo.has_preCalcs:
        algo.preCalcs = mod.preCalcs
        algo.needsPreCalc = True
    
    # store algo obj 
    #
    algoObjs[module_name] = algo
    


