
class Task( object ):
    #__slots__ = ( 'event', 'exception', 'request', 'response' )
    __slots__ = ( 'exception', 'request', 'response' )

    Empty = None

    def __init__( self, req, evt = None ):
        #self.event = evt or mp.Event()
        self.exception = None
        self.request = req
        self.response = None

    @staticmethod
    def is_empty( task ):
        return task.exception is None \
            and task.request is False \
            and task.response is True

    def set( self ):
        #self.event.set()
        pass

    def wait( self ):
        #self.event.wait()
        pass


Task.Empty = Task( False )
Task.Empty.exception = None
Task.Empty.response  = True
