
import logging
import multiprocessing as mp

from data import Task


class ProcessBase( mp.Process ):
    _id = 0

    def __init__( self, queue ):
        ProcessBase._id += 1
        super( ProcessBase, self ).__init__()

        #allow threads to be killed immediately
        self.id = ProcessBase._id
        self.daemon = True
        self.queue = queue
        self.is_running = False


    def process( self, request ):
        raise NotImplementedError( 'ProcessBase.process' )


    def run( self ):
        self.set_logger()
        while self.is_running:
            try:
                task = self.queue.get()
            except:
                self.logger.exception( 'ProcessBase.run' )


            if Task.is_empty( task ):
                self.queue.task_done()
                self.stop()
                return
            else:
                try:
                    task.response = self.process( task.request )
                except Exception as ex:
                    task.exception = ex
                finally:
                    self.queue.task_done()
                    task.set()


    def set_logger( self ):
        self.logger = mp.get_logger()


    def start( self ):
        logging.info( 'Starting ProcessBase...' )
        self.is_running = True
        super( ProcessBase, self ).start()


    #internal
    def stop( self ):
        self.logger.info( 'Stopping ProcessBase...' )
        self.is_running = False


class ProcessPool( object ):
    def __init__( self, proc_qty, proc_type = mp.Process, target = None, args = () ):
        self.is_running = False
        self.queue = mp.JoinableQueue()
        self.tasks = []
        self.procs = []

        new_args = [a for a in args]
        new_args.append( self.queue )
        for i in range( proc_qty ):
            if thread_type:
                t = proc_type( *new_args )
            #elif target:
            #    t = Thread( target=target )
            else:
                raise

            self.procs.append( t )

    def join_queue( self ):
        self.queue.join()
        return self

    def join_procs( self ):
        for proc in self.procs:
            if proc and proc.is_alive():
                proc.join()

        return self
        
    def put( self, req, synchronous = False ):
        task = Task( req )
        self.queue.put( task )

        if synchronous:
            task.wait()
        
        return task

    def start( self ):
        if self.is_running:
            raise RuntimeError( 'ProcessPool already started' )

        self.is_running = True
        logging.info( 'Starting ProcessPool...' )
        for proc in self.procs:
            proc.start()

        logging.info( '\tProcessPool started.' )
        return self

    def stop( self ):
        logging.info( 'Stopping ProcessPool...' )
        for proc in self.procs:
            self.queue.put( Task.Empty )

        logging.info( '\tProcessPool stopped.' )
        return self

