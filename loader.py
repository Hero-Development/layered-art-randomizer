#
# Layered Art Randomizer 
# © 2021, Hero Development, Inc dba Squeebo
#

#
# requirements:
# pip install pillow
#


import csv, logging, os, re, sys

__dir__ = os.path.dirname(os.path.realpath(__file__))

class LayerLoader:
  COLUMNS = (
    'z',
    'feature',
    'expression',
    'mils',
    'link:feature',
    'link:expression',
    'is_metadata',
    'display_type',
    'trait_type',
    'value',
    'path'
  )

  def __init__( self, root ):
    self.ROOT = root
    self.fd = open( 'traits.csv', 'w', newline='\n' )
    self.writer = csv.DictWriter( self.fd, self.COLUMNS )


  def __enter__( self ):
    self.writer.writeheader()
    return self

  def __exit__( self, type, value, traceback ):
    self.fd.flush()
    self.fd.close()
    
    

  @staticmethod
  def normalize( text ):
    return ' '.join( re.split( r'[^A-Za-z0-9]+', text ) ).title()


  def walk( self, path ):
    values = []
    for file in os.scandir( path ):
      next_path = file.path
      if file.is_dir():
        logging.info( f"Walking '{next_path}'" )
        self.walk( next_path )
      else:
        logging.info( f"Loading trait '{next_path}'..." )
        
        start = len( __dir__ )
        rel_path = next_path[start:]
        rel_path = rel_path.replace( '\\', '/' ).strip( '/' )
        logging.info( f"rel_path: '{rel_path}'" )

        start = len( self.ROOT )
        trait_path = path[start:]
        trait_type = self.normalize( trait_path )
        
        value = self.normalize( file.name[:file.name.rfind( '.' )] )
        if not trait_type:
          trait_type = value
          value = 'Default'


        logging.info( f"trait_type: '{trait_type}'" )
        logging.info( f"value: '{value}'" )
        values.append({
          'z':           0,
          'feature':     trait_type,
          'expression':  value,
          'mils':        1,
          'is_metadata': 1,
          'display_type': 'string',
          'trait_type':  trait_type,
          'value':       value,
          'path':        rel_path
        })
      
    if values:
      values.sort( key=lambda v: v['value'] )
      for value in values:
        self.writer.writerow( value )



if __name__ == '__main__':
  formatter = logging.Formatter( '[%(asctime)s] %(levelname)-8s %(filename)12.12s:%(lineno)3d %(message)s' )

  handler = logging.StreamHandler(sys.stdout)
  handler.setLevel(logging.DEBUG)
  handler.setFormatter(formatter)

  logger = logging.getLogger()
  logger.setLevel(logging.DEBUG)
  logger.addHandler(handler)

  print( sys.argv )


  path = __dir__
  if len( sys.argv ) >= 2:
    print( 'is_dir' )
    path = os.path.join( path, sys.argv[1] )

  with LayerLoader( path ) as loader:
    loader.walk( path )

