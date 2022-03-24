#
# Layered Art Randomizer 
# © 2021, Hero Development, Inc dba Squeebo
#

#
# requirements:
# pip install pillow
#

import csv, datetime, json, logging, os, random, signal, sys
from PIL import Image

__dir__ = os.path.dirname( os.path.realpath( __file__ ) )

class ImageProcessor( ProcessBase ):
  LOW_MEM = False
  RESIZE = None #( 1024, 1024 )

  def __init__( self, queue ):
    super( ImageProcessor, self ).__init__( queue )
    self.set_logger()

    self.traits = {}
    self.images_path = os.path.join( __dir__, '2-images' )
    self.load_traits( 'traits.csv' )


  def generate_image( self, item ):
    layers = {}
    for feature, expression in item.items():
      self.current_trait = None
      if feature != 'index':
        self.current_trait = current_trait = self.get_trait( feature, expression )

        if current_trait['path']:
          layers[ current_trait['z'] ] = self.get_image( current_trait )
        elif current_trait['expression']:
          self.logger.warning( f"{feature}: {expression} does not have a path"  )

    self.current_trait = None


    composite = None
    indices = sorted(layers.keys())
    for i in indices:
      if i in layers:
        if composite:
          try:
            #self.logger.info( "Appending layer {0} - {1}: {2}".format( i, layers[i]['feature'], layers[i]['expression'] ) )
            composite = Image.alpha_composite( composite, layers[ i ][ 'image' ] )
          except Exception as ex:
            self.logger.error( i )
            raise ex

        else:
          #self.logger.info( "Base layer {0} - {1}: {2}".format( i, layers[i]['feature'], layers[i]['expression'] ) )
          composite = layers[ i ][ 'image' ].copy()

      else:
        #self.logger.info( "Omit layer {0}".format( i ))
        pass


    if self.RESIZE:
      composite = composite.resize( self.RESIZE )


    save_as = os.path.join( self.images_path, '{0}.png'.format( item['index'] ) )
    composite.save( save_as )
    self.logger.info( "CREATED: Image {0}".format( item['index'] ) )


  def get_image( self, trait ):
    if self.LOW_MEM:
      trait = trait.copy()
      self.logger.info( "LOAD:  Image '{0}'".format( trait[ 'path' ] ) )
      trait['image'] = Image.open( trait[ 'path' ] ).convert('RGBA')
      return trait

    else:
      try:
        image = trait[ 'image' ]
        self.logger.debug( "CACHE: Use image '{0}'".format( trait[ 'path' ] ) )
        return trait

      except KeyError:
        self.logger.info( "LOAD:  Image '{0}'".format( trait[ 'path' ] ) )
        trait[ 'image' ] = Image.open( trait[ 'path' ] ).convert('RGBA')
        return trait


  def get_trait( self, feature, expression ):
    try:
      return self.traits[ feature ][ expression ]
    except KeyError as kex:
      self.logger.error( f'{feature}:{expression}' )
      raise kex


  def load_traits( self, path ):
    traits = {}
    all_paths_ok = True
    with open( path ) as data:
      i = 0
      reader = csv.DictReader( data )
      for row in reader:
        i += 1

        try:
          row['is_metadata'] = bool(int( row['is_metadata'] ))

        except KeyError:
          raise NotImplementedError( f"Row {i}: Each CSV item must provide the 'is_metadata' attribute" )

        except ValueError:
          row['is_metadata'] = False
          

        try:
          row['z'] = int( row['z'] )

        except KeyError:
          raise NotImplementedError( f"Row {i}: Each CSV item must provide the 'z' attribute" )

        except ValueError:
          raise NotImplementedError( f"Row {i}: Each CSV item must provide a numeric 'z' attribute" )


        try:
          row['mils'] = int( row['mils'] )
        except KeyError:
          row['mils'] = 0
          logging.warning( f"Row {i}: setting empty/missing mils to 0" )
          #raise NotImplementedError( "Each CSV item must provide the 'mils' attribute" )


        # fix the paths
        if row['path']:
          slices = row['path'].split( '/' )
          if len( slices ) == 1:
            slices = row['path'].split( '\\' )

          row['path'] = os.path.join( __dir__, *slices )
          if row['path'] and not os.path.exists( row['path'] ):
            all_paths_ok = False
            logging.error( row['path'] )


        # enforce uniqueness
        if row['feature'] in traits:
          if row['expression'] in traits[ row['feature'] ]:
            raise Exception( "Row {2}: Duplicate feature-expression: '{0}' '{1}'".format( row['feature'], row['expression'], i ) )

          else:
            traits[ row['feature'] ][ row['expression'] ] = row

        else:
          traits[ row['feature'] ] = {
            row['expression']: row
          }

        #logging.info( row )


    if all_paths_ok:
      logging.info( sorted(traits.keys()) )
      self.traits = traits

    else:
      raise Exception( "Missing resources" )


  def process( self, request ):
    item = json.loads( request )
    self.generate_image( item )


  def set_logger( self ):
    formatter = logging.Formatter( '[%(asctime)s] %(levelname)-8s %(filename)12.12s:%(lineno)3d %(message)s' )

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)

    self.logger = mp.get_logger()
    self.logger.setLevel(logging.DEBUG)
    self.logger.addHandler(handler)


  def start( self ):
    super( ImageProcessor, self ).start()




# 1-based
class TraitGenerator:

  #template = {}
  
  NAME = "#{0}"
  DESCRIPTION = ""
  QUANTITY = 500
  BASE_URL = ''

  LOW_MEM = False
  RESIZE = None #( 1024, 1024 )

  BASE_TRAITS = (
    'Background',
    'Body',
    'Clothes',
    'Eyes',
    'Hat',
    'Mouth',
    'Neck'
  )

  def __init__( self ):
    self.current_item = None
    self.current_trait = None

    self.continue_items = {}
    self.recipe_items = {}

    self.is_running = True
    self.queue = Queue()
    self.recipe_fd = None
    self.recipe_csv = None
    self.rules = []
    self.traits = {}

    self.stop_event = threading.Event()
    self.threads = []
    self.use_threads = 0


  def __enter__( self ):
    try:
      self.images_path = os.path.join( __dir__, '2-images' )
      os.mkdir( self.images_path )
    except FileExistsError:
      pass

    try:
      self.metadata_path = os.path.join( __dir__, '3-metadata' )
      os.mkdir( self.metadata_path )
    except FileExistsError:
      pass


    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    self.recipe_fd = open( os.path.join( __dir__, f'recipe-{ts}.csv' ), 'w', newline='\n' )
    return self


  def __exit__( self, exc_type, exc_val, exc_tb ):
    self.stop()
    self.close_recipes()


  def close_recipes( self ):
    if self.recipe_fd:
      self.recipe_fd.flush()
      self.recipe_fd.close()
      self.recipe_fd = None


  def configure( self ):
    args = sys.argv.copy()
    args.pop(0)
    for arg in args:
      key, value = arg.split( '=' )
      if key == '--continue':
        logging.info( 'CONFIGURE: Continuing recipes from {0}'.format( value ) )
        csv_path = os.path.join( __dir__, value )
        self.continue_items = self.load_items( csv_path )

      elif key == '--level':
        logging.info( 'CONFIGURE: Change log level {0}'.format( value ) )
        value = value.upper()
        logging.info( value )
        logger = logging.getLogger()
        logger.setLevel( value )

      elif key == '--quantity':
        logging.info( 'CONFIGURE: Overriding quantity from {0} to {1}'.format( self.QUANTITY, value ) )
        self.QUANTITY = int( value )

      elif key == '--recipes':
        logging.info( 'CONFIGURE: Blending recipes from {0}'.format( value ) )
        csv_path = os.path.join( __dir__, value )
        self.recipe_items = self.load_items( csv_path )

      elif key == '--threads':
        logging.info( 'CONFIGURE: Using {0} theads'.format( value ) )
        self.use_threads = int(value)

      else:
        logging.warn( f"Ignoring argument '{key}': '{value}'" )


  def load_items( self, csv_path ):
    row = -1
    loaded_items = {}
    with open( csv_path ) as csv_fd:
      reader = csv.DictReader( csv_fd )
      for item in reader:
        row += 1
        if self.is_valid( item, True ):
          key = tuple(sorted(item.items()))
          if key not in loaded_items:
            loaded_items[key] = item

        else:
          logging.warning( f"Row {row} is not valid" )
          self.current_item = item
          raise Exception( item )

    self.current_item = None
    logging.info( "{0} items loaded successfully".format( len( loaded_items ) ) )
    return loaded_items


  def load_traits( self, path ):
    traits = {}
    all_paths_ok = True
    with open( path ) as data:
      i = 0
      reader = csv.DictReader( data )
      for row in reader:
        i += 1

        try:
          row['is_metadata'] = bool(int( row['is_metadata'] ))

        except KeyError:
          raise NotImplementedError( f"Row {i}: Each CSV item must provide the 'is_metadata' attribute" )

        except ValueError:
          row['is_metadata'] = False
          

        try:
          row['z'] = int( row['z'] )

        except KeyError:
          raise NotImplementedError( f"Row {i}: Each CSV item must provide the 'z' attribute" )

        except ValueError:
          raise NotImplementedError( f"Row {i}: Each CSV item must provide a numeric 'z' attribute" )


        try:
          row['mils'] = int( row['mils'] )
        except KeyError:
          row['mils'] = 0
          logging.warning( f"Row {i}: setting empty/missing mils to 0" )
          #raise NotImplementedError( "Each CSV item must provide the 'mils' attribute" )


        # fix the paths
        if row['path']:
          slices = row['path'].split( '/' )
          if len( slices ) == 1:
            slices = row['path'].split( '\\' )

          row['path'] = os.path.join( __dir__, *slices )
          if row['path'] and not os.path.exists( row['path'] ):
            all_paths_ok = False
            logging.error( row['path'] )


        # enforce uniqueness
        if row['feature'] in traits:
          if row['expression'] in traits[ row['feature'] ]:
            raise Exception( "Row {2}: Duplicate feature-expression: '{0}' '{1}'".format( row['feature'], row['expression'], i ) )

          else:
            traits[ row['feature'] ][ row['expression'] ] = row

        else:
          traits[ row['feature'] ] = {
            row['expression']: row
          }

        #logging.info( row )
        

    if all_paths_ok:
      logging.info( sorted(traits.keys()) )
      self.traits = traits

    else:
      raise Exception( "Missing resources" )











  def check_distribution( self, items ):
    counts = {}
    for data in items:
      for feature, expression in data.items():
        if feature in counts:
          try:
            counts[ feature ][ expression ] += 1
          except KeyError:
            counts[ feature ][ expression ] = 1
        else:
          counts[ feature ] = { expression: 1 }

    for feature, values in counts.items():
      if feature == 'index':
        continue


      for expression in values:
        try:
          trait = self.get_trait( feature, expression )
          if trait['mils']:
            pct = counts[feature][expression] / float( trait['mils'] )

            # 10% margin of error
            margin = abs( 1 - pct )
            if margin < 1 and margin > 0.1:
              logging.warning( f"{feature}-{expression}: {pct}" )
              # TODO: if we throw some out, we should shuffle at the end

        except Exception as ex:
          logging.info( f"feature: {feature} expression: {expression}" )
          logging.exception( ex )
          raise ex


  def customize( self, new_items ):
    for rule in self.rules:
      if 'hits' not in rule or not rule['hits']:
        logging.error( 'Rule was not used' )
        logging.error( rule )
        #raise Exception( "Rule was not used" )

    i = 0
    for item in self.continue_items:
      item['index'] = i
      i += 1

    for item in new_items:
      item['index'] = i
      i += 1      


  def generate_items( self, new_items ):
    #TODO: self.generate_jsons()
    #TODO: metadata.csv
    #if regenerate
    #all_items = list(self.continue_items.values())
    #all_items.extend( new_items )

    columns = list(self.traits.keys())
    columns.insert( 0, 'index' )

    self.recipe_csv = csv.DictWriter( self.recipe_fd, columns )
    self.recipe_csv.writeheader()

    for item in self.continue_items:
      self.generate_json( item )

    for item in new_items:
      self.generate_json( item )

    self.close_recipes()
    #return



    #TODO: self.generate_images()
    #TODO: self.generate_images_mp()
    #TODO: self.generate_images_mt()
    #TODO: self.generate_images_st()

    '''
    if self.use_procs:
      raise NotImplementedError()

    '''
    if self.use_threads:
      #TODO: threads.ThreadPool
      # start the background threads
      self.threads = []
      for i in range( self.use_threads ):
        t = threading.Thread(target=self.process_image, daemon=False)
        t.start()
        self.threads.append( t )
        
      # enqueue images to generate
      for item in items:
        self.queue.put( item )

      # stop the background threads
      for t in self.threads:
        self.queue.put( None )

      self.queue.join()

    else:
      for item in self.continue_items:
        if self.is_running:
          self.current_item = item
          self.generate_image( item )

        else:
          break

      for item in new_items:
        if self.is_running:
          self.current_item = item
          self.generate_image( item )

        else:
          break


  def generate_image( self, item ):
    layers = {}
    for feature, expression in item.items():
      self.current_trait = None
      if feature != 'index':
        self.current_trait = current_trait = self.get_trait( feature, expression )

        if current_trait['path']:
          layers[ current_trait['z'] ] = self.get_image( current_trait )
        elif current_trait['expression']:
          logging.warning( f"{feature}: {expression} does not have a path"  )

    self.current_trait = None


    composite = None
    indices = sorted(layers.keys())
    for i in indices:
      if i in layers:
        if composite:
          try:
            #logging.info( "Appending layer {0} - {1}: {2}".format( i, layers[i]['feature'], layers[i]['expression'] ) )
            composite = Image.alpha_composite( composite, layers[ i ][ 'image' ] )

          except Exception as ex:
            logging.error( "Composite failed with layer '{0}:{1}'".format( layers[i]['feature'], layers[i]['expression'] ) )
            raise ex

        else:
          #logging.info( "Base layer {0} - {1}: {2}".format( i, layers[i]['feature'], layers[i]['expression'] ) )
          composite = layers[ i ][ 'image' ].copy()

        if self.LOW_MEM:
          layers[i]['image'].close()

      else:
        #logging.info( "Omit layer {0}".format( i ))
        pass


    if self.RESIZE:
      composite = composite.resize( self.RESIZE )


    save_as = os.path.join( self.images_path, '{0}.png'.format( item['index'] ) )
    composite.save( save_as )
    logging.info( "CREATED: Image {0}".format( item['index'] ) )


  def generate_json( self, item ):
    #logging.warning( item )
    self.recipe_csv.writerow( item )

    data = {
      "name": self.NAME.format( item['index'] ),
      "description": self.DESCRIPTION.format( item['index'] ),
      #"external_url": "",
      "image": '{0}{1}.png'.format( self.BASE_URL, item['index'] ),
      "attributes": [],
      "original": "https://gateway.pinata.cloud/ipfs/QmYxjWLWJ9FtSfx23xBL5Ee8nVgSvvT5tHTfBzQrb8LGQW/{0}.png".format( item['index'] )
    }


    data['attributes'] = self.finalize_traits( item )
    save_as = os.path.join( self.metadata_path, '{0}.json'.format( item['index'] ) )
    with open( save_as, 'w' ) as fp:
      json.dump( data, fp )


  def get_image( self, trait ):
    if self.LOW_MEM:
      trait = trait.copy()
      logging.info( "LOAD:  Image '{0}'".format( trait[ 'path' ] ) )
      trait['image'] = Image.open( trait[ 'path' ] ).convert('RGBA')
      return trait

    else:
      try:
        image = trait[ 'image' ]
        logging.debug( "CACHE: Use image '{0}'".format( trait[ 'path' ] ) )
        return trait

      except KeyError:
        logging.info( "LOAD:  Image '{0}'".format( trait[ 'path' ] ) )
        trait[ 'image' ] = Image.open( trait[ 'path' ] ).convert('RGBA')
        return trait


  def get_trait( self, feature, expression ):
    try:
      return self.traits[ feature ][ expression ]
    except KeyError as kex:
      logging.error( f'{feature}:{expression}' )
      raise kex



  def process_image( self ):
    while not self.stop_event.isSet():
      try:
        item = self.queue.get()
        if item is None:
          self.queue.task_done()
          break

        else:
          self.generate_image( item )
          self.queue.task_done()

      except Exception as ex:
        logging.exception( ex )
        self.queue.task_done()


  def randomize( self ):
    quantity = self.QUANTITY
    if self.continue_items:
      quantity -= len( self.continue_items )


    new_items = {}
    if self.recipe_items:
      new_items.update( self.recipe_items )
      quantity -= len( new_items )

      #break the ref
      self.recipe_items = {}


    i = -1;
    duplicate = 0
    invalid = 0
    self.weights, self.populations = self.compile_base_traits()
    while quantity:
      i += 1
      if duplicate > 10000:
        logging.warning( f"Remaining {quantity}" )
        raise Exception( "Too many duplicate items" )

      if invalid > 10000:
        logging.warning( f"Remaining {quantity}" )
        raise Exception( "Too many invalid items" )


      item = {}
      for feature in self.weights.keys():
        selected, = random.choices( self.populations[ feature ], weights=self.weights[ feature ] )
        item[ feature ] = selected


      self.randomize_extended_traits( item, i )   
      if self.is_valid( item ):
        key = tuple(sorted(item.items()))
        if key in self.continue_items or key in new_items:
          duplicate += 1

        else:
          quantity -= 1
          new_items[ key ] = item

      else:
        invalid += 1

    return list(new_items.values())


  def compile_base_traits( self ):
    weights = {}
    populations = {}
    for feature in self.BASE_TRAITS:
      traits = [ trait for trait in self.traits[ feature ].values() if trait['mils'] ]
      if traits:
        populations[ feature ] = tuple([ v['expression'] for v in traits ])
        cw = [ v['mils'] for v in traits if v['mils'] > 0 ]
        if len(cw) == 0:
          logging.warning( "Feature '{0}' doesn't have any traits to randomize".format( feature ) )
        elif len(set(cw)) == 1:
          weights[ feature ] = None
        else:
          weights[ feature ] = tuple(cw)
      else:
        logging.warning( "Feature '{0}' doesn't have any traits to randomize".format( feature ) )


    logging.info( weights )
    logging.info( populations )
    return ( weights, populations )


  def process_links( self, item ):
    if 'link:feature' not in item:
      return


    source = item.copy()
    for key, value in source.items():
      while key:
        trait = self.get_trait( key, value )
        key = trait['link:feature']
        if key:
          if trait['link:expression'] == '*':
            value = self.randomize_trait( key )
          else:
            value = trait[ 'link:expression' ]

          #logging.info( '{0} :: {1}'.format( key, value ) )
          item[ key ] = value

        else:
          break


  def randomize_extended_traits( self, item, i ):
    logging.info( "Processing item {0}".format( i ) )
    self.process_links( item )


  def randomize_trait( self, feature, **kwargs ):
    traits = [trait for trait in self.traits[ feature ].values()]

    if kwargs:
      for key, value in kwargs.items():
        traits = [ trait for trait in traits if trait[ key ] == value ]
        if not traits:
          logging.warning( f"No traits found for {feature} :: '{key}'='{value}'" )

    if len( traits ) > 1:
      return self.randomize_traits( traits )
    elif len( traits ) == 1:
      return traits[0]['expression']
    else:
      return ''


  def randomize_traits( self, traits ):
    population = tuple([ t['expression'] for t in traits ])
    weights = tuple([ t['mils'] for t in traits ])
    if len(set(weights)) == 1:
      weights = None

    #logging.info( weights )
    #logging.info( population )
    selected, = random.choices( population, weights=weights )
    return selected


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


  def finalize_traits( self, item ):
    #TODO: add custom/derived traits here
    json_traits = item.copy()


    remove = ()
    for key in remove:
      if key in json_traits:
        del json_traits[ key ]

    #TODO: write consolidated metadata
    del json_traits['index']

    attributes = []
    for trait_name, value in json_traits.items():
      try:
        trait = self.get_trait( trait_name, value )
      except KeyError:
        raise KeyError( f'{trait_name}::{value}' )

      if trait['is_metadata']:
        if trait['display_type'] == 'string':
          attributes.append({
            "trait_type": trait['trait_type'],
            "value":      trait['value']
          })
        elif trait['display_type'] == 'number':
          attributes.append({
            "trait_type": trait['trait_type'],
            "value":      int(trait['value'])
          })
        else:
          display_type = trait['display_type']
          raise NotImplementedError( f"finalize_traits() '{display_type}'" )

    return attributes


  @staticmethod
  def is_conflict( item, rule ):
    if 'is_enabled' in rule:
      if rule['is_enabled']:
        pass
      else:
        return False
    else:
      pass


    if TraitGenerator.is_match( item, rule['match'] ):
      for conflict in rule['conflicts']:
        if TraitGenerator.is_match( item, conflict ):
          try:
            rule['hits'] += 1
          except KeyError:
            rule['hits'] = 1

          return True

    return False


  @staticmethod
  def is_match( item, match ):
    if 'is_enabled' in match:
      if match['is_enabled']:
        pass
      else:
        return False
    else:
      pass

    if match['feature'] in item and item[ match['feature'] ]:
      expression = item[ match['feature'] ]
      if 'is_any' in match and match['is_any']:
        return bool( expression )

      if expression in match['expressions']:
        return True

    return False


  def is_valid( self, item, throw=False ):
    if not self.rules:
      rules_path = os.path.join( __dir__, 'rules.json' )
      with open( rules_path ) as fd:
        self.rules = json.load( fd )

    for rule in self.rules:
      if rule['type'] == 'conflict':
        if self.is_conflict( item, rule ):
          if throw:
            raise Exception( rule )
          else:
            return False

    return True



if __name__ == '__main__':
  formatter = logging.Formatter( '[%(asctime)s] %(levelname)-8s %(filename)12.12s:%(lineno)3d %(message)s' )

  handler = logging.StreamHandler(sys.stdout)
  handler.setLevel(logging.DEBUG)
  handler.setFormatter(formatter)

  logger = logging.getLogger()
  logger.setLevel(logging.DEBUG)
  logger.addHandler(handler)

  ui_thread = threading.current_thread()
  logging.info( f'UI thread is daemon: {ui_thread.daemon}' )

  random.seed()


  recipe0 = {
    "index":   0,
    "Background": "Red aqua",
    "Body":    "4 Gold fish",
    "Clothes": "Flannel 2",
    "Eyes":    "Suprised",
    "Hat":     "bone through skull",
    "Mouth":   "Buck teeth",
    "Neck":    "Chain on neck shirtless"
  }

  test0 = json.dumps( recipe0 )

  #mp.set_start_method( 'spawn' )
  queue = mp.JoinableQueue()
  
  
  proc = ImageProcessor( queue )
  proc.start()
  logging.info( '... started' )

  queue.put( Task(test0) )
  queue.join()


  # poison pill
  queue.put( Task.Empty )
  proc.join()
  logging.info( 'proc joined' )
  exit()



  start = datetime.datetime.now()
  with TraitGenerator() as gen:
    try:
      if hasattr( signal, 'SIGBREAK' ):
        # Windows: Ctrl + Break (Pause)
        signal.signal( signal.SIGBREAK, gen.signal_interrupt )

      # Linux: Ctrl + C
      signal.signal( signal.SIGINT,   gen.signal_interrupt )

      gen.load_traits( 'traits.csv' )
      gen.configure()
      new_items = gen.randomize()
      if new_items:
        logging.info( "{0} random items".format( len( new_items ) ) )
      else:
        logging.warning( "{0} random items".format( len( new_items ) ) )

      #gen.check_distribution( items )
      gen.continue_items = gen.continue_items.values()
      #random.sample(new_items, k=len(new_items))
      #gen.randomize_last( new_items )

      gen.customize( new_items )
      gen.generate_items( new_items )


    except Exception as ex:
      logging.exception( ex )
      
      if gen.current_item:
        logging.error( gen.current_item )

      if gen.current_trait:
        logging.error( gen.current_trait )

    finally:
      duration = datetime.datetime.now() - start
      logging.info( duration )
