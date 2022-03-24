
import logging
from Queue import Queue
from threading import Thread


class ThreadBase( Thread ):
    _id = 0

    def __init__( self, queue ):
        ThreadBase._id += 1
        super( ThreadBase, self ).__init__()

        #allow threads to be killed immediately
        self.id = ThreadBase._id
        self.daemon = True
        self.queue = queue
        self.is_running = False

    def process( self, request ):
        raise NotImplementedError( 'ThreadBase.process' )

    def run( self ):
        while self.is_running:
            try:
                task = self.queue.get()
            except:
                logging.exception( 'ThreadBase.run' )


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

    def start( self ):
        logging.info( 'Starting ThreadBase...' )
        self.is_running = True
        super( ThreadBase, self ).start()

    def stop( self ):
        logging.info( 'Stopping ThreadBase...' )
        self.is_running = False


class ThreadPool( object ):
    def __init__( self, thread_qty, thread_type = Thread, target = None, args = () ):
        self.is_running = False
        self.queue = Queue()
        self.tasks = []
        self.threads = []

        new_args = [a for a in args]
        new_args.append( self.queue )
        for i in range( thread_qty ):
            if thread_type:
                t = thread_type( *new_args )
            #elif target:
            #    t = Thread( target=target )
            else:
                raise

            self.threads.append( t )

    def join_queue( self ):
        self.queue.join()
        return self

    def join_threads( self ):
        for thread in self.threads:
            if thread and thread.is_alive():
                thread.join()

        return self
        
    def put( self, req, synchronous = False ):
        task = Task( req )
        self.queue.put( task )

        if synchronous:
            task.wait()
        
        return task

    def start( self ):
        if self.is_running:
            raise RuntimeError( 'ThreadPool already started' )

        self.is_running = True
        logging.info( 'Starting ThreadPool...' )
        for thread in self.threads:
            thread.start()

        logging.info( '\tThreadPool started.' )
        return self

    def stop( self ):
        logging.info( 'Stopping ThreadPool...' )
        for thread in self.threads:
            self.queue.put( Task.Empty )

        logging.info( '\tThreadPool stopped.' )
        return self

