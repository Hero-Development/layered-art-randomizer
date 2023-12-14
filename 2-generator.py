#
# Layered Art Randomizer 
# © 2021, Hero Development, Inc dba Squeebo
#

#
# requirements:
# pip install pillow
#
# optional:
# pip install googleapiclient
# pip install oauth2client
#

import datetime, logging, os, random, sys, threading
from impl import ImageMaker

__dir__ = os.path.dirname( os.path.realpath( __file__ ) )


class TraitGenerator(ImageMaker):
  pass


if __name__ == '__main__':
  TraitGenerator.default_logging()

  ui_thread = threading.current_thread()
  logging.info( f'UI thread is daemon: {ui_thread.daemon}' )

  start = datetime.datetime.now()
  gen = TraitGenerator()

  try:
    gen.register_interrupts()
    gen.configure()
    gen.init()
    #TODO: traits path
    #TODO: load continue
    #TODO: load recipes
    if gen.gsheet_id:
      gen.load_gsheet( gen.gsheet_id, 0 )
    else:
      gen.load_traits()

    gen.validate_rules()
    gen.randomize()
    #gen.randomize_last()
    #gen.customize()
    gen.generate_items()

  except Exception as ex:
    logging.exception( ex )
    
    if gen.current_item:
      logging.error( gen.current_item )

    if gen.current_trait:
      logging.error( gen.current_trait )

  finally:
    duration = datetime.datetime.now() - start
    logging.info( duration )
