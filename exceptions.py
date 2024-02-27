
class WWError(Exception):
    pass

class NoElectrodes(WWError):
    def __init__(self, message = "Invalid input provided"):
        self.message = message
        super().__init__(self.message)