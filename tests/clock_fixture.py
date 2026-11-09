class Clock:
    def __init__(self): self.now=2000000000.; self.waits=[]
    def time(self): return self.now
    def sleep(self, seconds): self.waits.append(seconds); self.now+=seconds
