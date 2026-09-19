from datetime import datetime
class ActivityBus:
    def __init__(self): self.listeners=[]
    def subscribe(self,callback): self.listeners.append(callback)
    def emit(self,message):
        line=f'[{datetime.now():%H:%M:%S}] {message}'
        for cb in list(self.listeners):
            try: cb(line)
            except Exception: pass
