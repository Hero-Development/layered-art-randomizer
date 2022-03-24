
import inspect

class Error( object ):
    def __init__( self, ex, traceback = None ):
        self.ex = ex
        self.traceback = traceback
        self.type = type( ex )
        self.module = inspect.getmodule( self.type )

    def get_args( self ):
        return self.ex.args

    def get_full_name( self ):
        return '%s.%s' % ( self.module.__name__, self.type.__name__ )

    def get_message( self ):
        return self.ex.message

    def get_module( self ):
        return self.module

    def get_module_name( self ):
        return self.module.__name__

    def get_type( self ):
        return self.type

    def get_type_name( self ):
        return self.type.__name__

    def __str__( self ):
        args = [ '"{}"'.format( a ) if type( a ) is str else str( a ) for a in self.ex.args ]
        return '%s.%s( %s )' % ( self.module.__name__, self.type.__name__, ', '.join( args ) )
