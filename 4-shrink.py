#
# Layered Art Randomizer 
# © 2021, Hero Development, Inc dba Squeebo
#

#
# requirements:
# pip install pillow
#

import csv, datetime, json, logging, math, os, random, signal, sys, threading, time
from queue import Queue
from threading import Thread
from PIL import Image

#google sheets
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient import discovery

__dir__ = os.path.dirname( os.path.realpath( __file__ ) )


class TraitGenerator:
  def __init__(self):
    self.is_running = True
    self.queue = Queue()
    self.stop_event = threading.Event()
    self.threads = []

    self.base_path = __dir__
    self.images_path = os.path.join( __dir__, '2-images' )
    self.thumbs_path = os.path.join( __dir__, '4-thumbs' )

    self.use_procs = 0
    self.use_threads = 0

    self.RESIZE = (2000,2000)


  def __exit__(self, exc_type, exc_val, exc_tb):
    self.stop()


  def init(self):
    try:
      self.images_path = os.path.join( self.base_path, '2-images' )
      os.mkdir( self.images_path )
    except FileExistsError:
      pass

    try:
      self.thumbs_path = os.path.join( self.base_path, '4-thumbs' )
      os.mkdir( self.thumbs_path )
    except FileExistsError:
      pass


  def generate_thumbs(self):
    if False and self.use_procs:
      raise NotImplementedError()


    elif False and self.use_threads:
      # start the background threads
      self.threads = []
      for i in range( self.use_threads ):
        t = threading.Thread(target=self.process_image, daemon=False)
        t.start()
        self.threads.append( t )
        
      # enqueue images to generate
      for item in new_items:
        self.queue.put( item )

      # stop the background threads
      for t in self.threads:
        self.queue.put( None )

      self.queue.join()

    else:
      for i in range(8888):
        if self.is_running:
          from_path = os.path.join(self.images_path, "{0}.png".format(i))
          to_path = os.path.join(self.thumbs_path, "{0}.jpg".format(i))
          if os.path.isfile(from_path) and not os.path.isfile(to_path):
            from_image = Image.open(from_path)
            resized = from_image.resize(self.RESIZE)
            
            (_, ext) = os.path.splitext(to_path)
            if ext.lower() == '.jpg':
              # if converting to jpg (non-alpha)
              converted = resized.convert('RGB')
              converted.save(to_path)
              converted.close()
              resized.close()

            else:
              resized.save(to_path)
              resized.close()

            from_image.close()
            logging.info("CREATED: Image {0}".format(i))

        else:
          break



  # our server listens for "interrupt" CTRL + C
  def signal_interrupt( self, sig, frame ):
    if sig == signal.SIGINT:
      logging.warning( 'Received: signal.SIGINT( {} )'.format( sig ) )
      self.stop()

    elif sig == signal.SIGBREAK:
      logging.warning( 'Received: signal.SIGBREAK( {} )'.format( sig ) )
      self.stop()    

    else:
      logging.warning( 'Unsupported signal: {}'.format( sig ) )


  def stop( self ):
    if not self.stop_event.is_set():
      self.stop_event.set()
      self.is_running = False



if __name__ == '__main__':
  formatter = logging.Formatter( '[%(asctime)s] %(levelname)-8s %(filename)12.12s:%(lineno)3d %(message)s' )

  handler = logging.StreamHandler(sys.stdout)
  handler.setLevel(logging.INFO)
  handler.setFormatter(formatter)

  logger = logging.getLogger()
  logger.setLevel(logging.INFO)
  logger.addHandler(handler)

  ui_thread = threading.current_thread()
  logging.info( f'UI thread is daemon: {ui_thread.daemon}' )

  start = datetime.datetime.now()
  gen = TraitGenerator()

  try:
    if hasattr( signal, 'SIGBREAK' ):
      # Windows: Ctrl + Break (Pause)
      signal.signal( signal.SIGBREAK, gen.signal_interrupt )

    # Linux: Ctrl + C
    signal.signal( signal.SIGINT,   gen.signal_interrupt )

    gen.init()
    gen.generate_thumbs()

  except Exception as ex:
    logging.exception( ex )

  finally:
    duration = datetime.datetime.now() - start
    logging.info( duration )
