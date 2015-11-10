

class Logger():
    def print_msg(self, msg):
        print(msg)

    def __init__(self):
        self.debug = self.print_msg
        self.info = self.print_msg

def getLogger(name):
    return Logger()