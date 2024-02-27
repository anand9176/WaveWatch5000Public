# some cnxn details...
#
from . import LiveExportDefs

local = False

# If you feel this file is within a secure system, you can add your private 
# key here in plain text, so you dont needn't enter it each time (if left blank, you are prompted).
#
privateKeyPass = ''

dumpPath = ''
address = LiveExportDefs.DEFAULT_BUS_HOST
ampqPort = 5671
if local:
    address = 'localhost'
    ampqPort = 5672

# exchanges to subscribe to
#
exchgSubs = []# add some necessary ones, and exclude others
for exchange in LiveExportDefs.DEFAULT_SUBSCRIPTIONS:
    
    if exchange in ('HMB.PRESENCE', 'EX.CMD'):# always subscribed
        exchgSubs.append(exchange)
    else:
        #exchg = exchange.replace('EX.', '')
        #if not self.callingNode.parm(exchg).eval(): continue
        exchgSubs.append(exchange)# ^^!! no exclusion interfce setup currently - ATM can just edit them out of LiveExportDefs.DEFAULT_SUBSCRIPTIONS
