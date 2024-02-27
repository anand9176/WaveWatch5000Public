
# set nb threads numpy BLAS/LAPACK libs use for parallelism (so work happily with ours)
#   >> need to set prior to (any, potentially nested) numpy import
#
from os import environ
nbThreads = '16'
#environ['OMP_NUM_THREADS'] = nbThreads
if 0:# other libs, may need to set it for too
    environ['OPENBLAS_NUM_THREADS'] = nbThreads
    environ['MKL_NUM_THREADS'] = nbThreads
    environ['VECLIB_MAXIMUM_THREADS'] = nbThreads
    environ['NUMEXPR_NUM_THREADS'] = nbThreads

from WW_GUI import WW_GUI
from WW_cnxn import WW_cnxn


from algos import algoObjs # /algos/__init__.py does some wrapping prep work on all the arb, custom algos found there. Reload the package to refresh.

import numpy as np
import scipy

import threading, time, itertools, os, enum, importlib, math

from time import time as curTime
from pprint import pprint as pp, pformat as pf
