# not much of a 'factory', yet
#

compute = None# is assigned from the custom modules when they are imported

class Algo(object):

    def __init__(self, customProps):

        self.props = {# defaults...
            'guiName' : 'unamed algorithm',
            'guiName_short' : 'N/A',
            'guiColor' : 'red',
            'plotType' : 'basicLineMenu',
            'guiMenu' : None,
        }
        self.props.update(customProps)# User-authored
        
        # turn the props into inst attributes
        #
        for propName, propValue in self.props.items():
            setattr(self, propName, propValue)
    
    
    def compute(self, data):
        return compute(data)# data will be passed around as ref (and a numpy view at that), so shouldnt be a hit
    
    def preCompute(self):
        ...
    
    def preCalcs(self):
        ...
