#
# Layered Art Randomizer 
# © 2021, Hero Development, Inc dba Squeebo
#

#
# requirements:
# pip install pillow
#


import csv, json, logging, os, random, re, shutil, sys

__dir__ = os.path.dirname(os.path.realpath(__file__))

class BulkRandomizer:
  FOLDERS = (
    '1',
    '2',
    '3'
  )


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

    return self


  def __exit__( self, type, value, traceback ):
    pass


  def gather( self, base_path ):
    all_files = []
    for folder in BulkRandomizer.FOLDERS:
      full_path = os.path.join( base_path, folder, '2-images' )
      for file in os.scandir( full_path ):
        if file.is_dir():
          logging.info( f"Ignoring folder '{file.path}'" )
          continue

        if file.name[0] == '.':
          logging.info( f"Ignoring '{file.path}'" )
          continue

        all_files.append( file.path )


    logging.info( 'Shuffling {0} files...'.format( len( all_files ) ) )
    rando_files = random.sample(all_files, k=8400)
    
    index = -1
    for image_path in rando_files:
      index += 1
      dirname = os.path.dirname( os.path.dirname( image_path ) )
      filename = os.path.basename( image_path )
      basename, ext = os.path.splitext( filename )
      
      numeral = re.match( '^(\d+)', basename ).group(0)
      json_path = os.path.join( dirname, '3-metadata', f'{numeral}.json' )


      with open( json_path ) as fd:
        metadata = json.load( fd )

      metadata['name'] = f'MEFaverse {index}'
      metadata['description'] = f'MEFaverse {index}'
      metadata['image'] = f'https://mint.mefaverse.io/images/{index}.png'
      save_as = os.path.join( self.metadata_path, f'{index}.json' )
      with open( save_as, 'w' ) as fd:
        json.dump( metadata, fd )


      image_dest = os.path.join( self.images_path, f'{index}.png' )
      shutil.copyfile(image_path, image_dest)
      
      if index > 30:
        break


    logging.info( 'Shuffled {0} files'.format( index ) )


if __name__ == '__main__':
  formatter = logging.Formatter( '[%(asctime)s] %(levelname)-8s %(filename)12.12s:%(lineno)3d %(message)s' )

  handler = logging.StreamHandler(sys.stdout)
  handler.setLevel(logging.DEBUG)
  handler.setFormatter(formatter)

  logger = logging.getLogger()
  logger.setLevel(logging.DEBUG)
  logger.addHandler(handler)

  print( sys.argv )

  base_path = __dir__
  if len( sys.argv ) >= 2:
    print( 'is_dir' )
    base_path = os.path.join( base_path, sys.argv[1] )
  
  with BulkRandomizer() as rando:
    rando.gather( base_path )

