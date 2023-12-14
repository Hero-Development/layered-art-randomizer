
import csv, datetime, json, logging, os, random, signal, sys, threading
import multiprocessing as mp
from queue import Queue
from PIL import Image

# google sheets
from googleapiclient import discovery
from oauth2client.service_account import ServiceAccountCredentials

__dir__ = os.path.dirname(os.path.realpath(__file__))


class TraitManager(object):
  def __exit__(self, exc_type, exc_val, exc_tb):
    self.close_recipes()


  def __init__(self):
    random.seed()

    self.recipe_fd = None
    self.recipe_path = None
    self.recipe_csv = None

    # paths
    self.base_path = __dir__
    self.metadata_path = os.path.join(__dir__, '3-metadata')
    self.rules_path = os.path.join(__dir__, 'rules.json')

    # scalars
    self.current_item = None
    self.gsheet_id = None

    # vectors
    self.continue_items = {}
    self.new_items = []
    self.recipe_items = {}
    self.rules = []
    self.traits = {}
    self.use_procs = 0
    self.use_threads = 0

    # TODO: self.config
    self.BASE_TRAITS = []
    self.CREATE_IMAGES = True
    self.CREATE_METADATA = True
    self.LOW_MEM = False
    self.QUANTITY = 0
    self.RESIZE = None
    self.START_IDX = 0
    self.METADATA_FORMAT = {
      "name": "",
      "description": "",
      "image": ""
    }


  def check_distribution(self):
    raise NotImplementedError()

    counts = {}
    for data in items:
      for feature, expression in data.items():
        if feature in counts:
          try:
            counts[feature][expression] += 1
          except KeyError:
            counts[feature][expression] = 1
        else:
          counts[feature] = { expression: 1 }

    for feature, values in counts.items():
      if feature == 'index':
        continue


      for expression in values:
        try:
          trait = self.get_trait(feature, expression)
          if trait['mils']:
            pct = counts[feature][expression] / float(trait['mils'])

            # 10% margin of error
            margin = abs(1 - pct)
            if margin < 1 and margin > 0.1:
              logging.warning(f"{feature}-{expression}: {pct}")
              # TODO: if we throw some out, we should shuffle at the end

        except Exception as ex:
          logging.info(f"feature: {feature} expression: {expression}")
          logging.exception(ex)
          raise ex


  def close_recipes(self):
    if self.recipe_fd:
      self.recipe_fd.flush()
      self.recipe_fd.close()
      self.recipe_fd = None


  def compile_base_traits(self):
    weights = {}
    populations = {}
    for feature in self.BASE_TRAITS:
      traits = [trait for trait in self.traits[feature].values() if trait['mils']]
      if traits:
        cw   = [v['mils']       for v in traits if v['mils'] > 0]
        pops = [v['expression'] for v in traits if v['mils'] > 0]
        if len(cw) == 0:
          logging.warning("Feature '{0}' doesn't have any traits to randomize".format(feature))
        elif len(set(cw)) == 1:
          weights[feature] = None
          populations[feature] = tuple(pops)
        else:
          weights[feature]     = tuple(cw)
          populations[feature] = tuple(pops)
      else:
        logging.warning("Feature '{0}' doesn't have any traits to randomize".format(feature))


    logging.debug(weights)
    logging.debug(populations)
    return (weights, populations)


  def configure(self):
    args = sys.argv.copy()
    args.pop(0)

    for arg in args:
      key, value = arg.split('=')
      if key == '--config':
        # TODO: is path rooted?
        logging.info(value)
        
        config = {}
        with open(value) as fd:
          config = json.load(fd)

        for (key, value) in config.items():
          #logging.info((key, value))
          # if key in ():
          setattr(self, key, value)
    

    for arg in args:
      key, value = arg.split('=')
      if key == '--config':
        pass

      elif key == '--continue':
        # TODO: is path rooted?
        if value[0] == '/':
          csv_path = value
        else:
          csv_path = os.path.join(self.base_path, value)

        logging.info('CONFIGURE: Continuing recipes from {0}'.format(csv_path))
        self.continue_items = self.load_items(csv_path)

      elif key == '--level':
        logging.info('CONFIGURE: Change log level {0}'.format(value))
        value = value.upper()
        logging.info(value)
        logger = logging.getLogger()
        logger.setLevel(value)

      elif key == '--quantity':
        logging.info('CONFIGURE: Overriding quantity from {0} to {1}'.format(self.QUANTITY, value))
        self.QUANTITY = int(value)

      elif key == '--recipes':
        # TODO: is path rooted?
        if value[0] == '/':
          csv_path = value
        else:
          csv_path = os.path.join(self.base_path, value)

        logging.info('CONFIGURE: Blending recipes from {0}'.format(value))
        self.recipe_items = self.load_items(csv_path)

      elif key == '--threads':
        logging.info('CONFIGURE: Using {0} threads'.format(value))
        self.use_threads = int(value)

      else:
        logging.warning(f"Ignoring argument '{key}': '{value}'")


  def customize(self):
    for rule in self.rules:
      if 'hits' not in rule or not rule['hits']:
        logging.error('Rule was not used')
        logging.error(rule)
        #raise Exception("Rule was not used")

    '''
    TODO
    do the continue_items have 'index'?
    if so, get max, and skip to new_items
    else, write to index
    '''


    i = 0
    for item in self.continue_items:
      item['index'] = i
      i += 1


    #extra = []
    for item in self.new_items:
      item['index'] = i
      i += 1


  @staticmethod
  def default_logging():
    # TODO: staticmethod
    formatter = logging.Formatter('[%(asctime)s] %(levelname)-8s %(filename)12.12s:%(lineno)3d %(message)s')

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    handler.setFormatter(formatter)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)


  def finalize_traits(self, item):
    #TODO: add custom/derived traits here
    json_traits = item.copy()


    remove = ()
    for key in remove:
      if key in json_traits:
        del json_traits[key]

    #TODO: write consolidated metadata
    del json_traits['index']

    attributes = []
    for trait_name, value in json_traits.items():
      try:
        trait = self.get_trait(trait_name, value)
      except KeyError:
        logging.warning('--> row: {}'.format(item['index']))
        raise KeyError(f'{trait_name}::{value}')

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
          raise NotImplementedError(f"finalize_traits() '{display_type}'")

    return attributes


  def generate_items(self):
    gen_items = []
    all_items = [*self.continue_items, *self.new_items]
    for idx in range(self.START_IDX, len(all_items)):
      gen_items.append(all_items[idx])


    columns = list(self.traits.keys())
    columns.insert(0, 'index')

    # TODO: open_recipes()
    self.recipe_fd = open(self.recipe_path, 'w', newline='\n')
    self.recipe_csv = csv.DictWriter(self.recipe_fd, columns)
    self.recipe_csv.writeheader()

    
    for item in gen_items:
      try:
        self.recipe_csv.writerow(item)
      except ValueError as vErr:
        logging.error(item)
        raise vErr

    self.close_recipes()


    if self.CREATE_METADATA:
      for item in gen_items:
        self.generate_json(item)


  def generate_json(self, item):
    #TODO: offset
    data = {}
    for key, value in self.METADATA_FORMAT.items():
      data[key] = value.format(index=item['index'])

    data['attributes'] = self.finalize_traits(item)
    save_as = os.path.join(self.metadata_path, '{0}.json'.format(item['index']))
    with open(save_as, 'w') as fp:
      json.dump(data, fp)


  def get_trait(self, feature, expression):
    try:
      return self.traits[feature][expression]
    except KeyError as kex:
      logging.error(f'{feature}:{expression}')
      raise kex


  def get_traits(self, feature, **kwargs):
    traits = [trait for trait in self.traits[feature].values()]

    selected = {}
    for key, values in kwargs.items():
      count = 0
      for trait in traits:
        if trait[key] in values:
          count += 1
          selected[trait['expression']] = trait
          
      if not count:
        logging.warning(f"No traits found for {feature} :: '{key}'='{value}'")

    return selected.values()


  def init(self):
    try:
      self.metadata_path = os.path.join(self.base_path, '3-metadata')
      os.mkdir(self.metadata_path)
    except FileExistsError:
      pass


    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    self.recipe_path = os.path.join(self.base_path, f'recipe-{ts}.csv')
    self.rules_path = os.path.join(self.base_path, 'rules.json')

  @classmethod
  def is_item_allowed(cls, item, rule):
    for allow in rule['allowed']:
      if cls.is_item_match(item, allow):
        try:
          rule['hits'] += 1
        except KeyError:
          rule['hits'] = 1

        return True

    return False


  @classmethod
  def is_item_denied(cls, item, rule):
    for denied in rule['denied']:
      if cls.is_item_match(item, denied):
        try:
          rule['hits'] += 1
        except KeyError:
          rule['hits'] = 1

        return True

    return False


  @staticmethod
  def is_item_match(item, match):
    if TraitGenerator.is_match_enabled(match):
      if match['feature'] in item and item[match['feature']]:
        expression = item[match['feature']]
        if 'is_any' in match and match['is_any']:
          return bool(expression)

        if expression in match['expressions']:
          return True

    return False


  def is_item_valid(self, item, throw=False):
    self.validate_rules()

    for rule in self.rules:
      if not self.is_rule_enabled(rule):
        continue

      if not self.is_item_match(item, rule['match']):
        continue

      if rule['type'] == 'allow':
        if not self.is_item_allowed(item, rule):
          if throw:
            raise Exception(rule)
          else:
            return False

      elif rule['type'] == 'deny':
        if self.is_item_denied(item, rule):
          if throw:
            raise Exception(rule)
          else:
            return False

      elif rule['type'] == 'info':
        #ignore this
        pass

      else:
        raise Exception("Unsupported rule type: {0}".format(rule['type']))

    return True


  @staticmethod
  def is_match_enabled(match):
    if 'is_enabled' in match:
      return match['is_enabled']
    else:
      return True


  @staticmethod
  def is_rule_enabled(rule):
    if 'is_enabled' in rule:
      return rule['is_enabled']
    else:
      return True


  def load_gsheet(self, spreadsheet_id, sheet_index):
    scope = [
      'https://www.googleapis.com/auth/spreadsheets',
      "https://www.googleapis.com/auth/drive"
    ]

    credentials = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    service = discovery.build('sheets', 'v4', credentials=credentials)

    request = service.spreadsheets().get(spreadsheetId=spreadsheet_id, ranges=[], includeGridData=True)
    response = request.execute()

    rows = []
    for data in response['sheets'][sheet_index]['data']:
      # load keys
      keys = []
      for row in data['rowData']:
        for cell in row['values']:
          if 'formattedValue' in cell:
            keys.append(cell['formattedValue'])
          else:
            break

        break


      # load values
      idx = -1
      for row in data['rowData']:
        idx += 1
        if idx:
          logging.debug("row "+ str(idx))
          if 'values' in row and 'formattedValue' in row['values'][0]:
            values = []
            for i in range(len(keys)):
              try:
                cell = row['values'][i]
                values.append(cell['formattedValue'])
              except (IndexError, KeyError):
                values.append('')

            row = dict(zip(keys, values))
            logging.debug(row)
            rows.append(row)

          else:
            break

      break


    #process
    i = 0
    traits = {}
    all_paths_ok = True
    for row in rows:
      i += 1

      try:
        row['is_metadata'] = bool(int(row['is_metadata']))
      except KeyError:
        raise NotImplementedError(f"Row {i}: Each CSV item must provide the 'is_metadata' attribute")
      except ValueError:
        row['is_metadata'] = False
        

      try:
        row['z'] = int(row['z'])
      except KeyError:
        raise NotImplementedError(f"Row {i}: Each CSV item must provide the 'z' attribute")
      except ValueError:
        raise NotImplementedError(f"Row {i}: Each CSV item must provide a numeric 'z' attribute")


      try:
        row['mils'] = int(row['mils'])
      except KeyError:
        row['mils'] = 0
        logging.warning(f"Row {i}: setting empty/missing mils to 0")
        #raise NotImplementedError("Each CSV item must provide the 'mils' attribute")


      # fix the paths
      if row['path']:
        slices = row['path'].split('/')
        if len(slices) == 1:
          slices = row['path'].split('\\')

        row['path'] = os.path.join(self.layers_path, *slices)
        if row['path'] and not os.path.exists(row['path']):
          all_paths_ok = False
          logging.error(row['path'])


      # enforce uniqueness
      if row['feature'] in traits:
        if row['expression'] in traits[row['feature']]:
          raise Exception("Row {2}: Duplicate feature-expression: '{0}' '{1}'".format(row['feature'], row['expression'], i))

        else:
          traits[row['feature']][row['expression']] = row

      else:
        traits[row['feature']] = {
          row['expression']: row
        }

      #logging.info(row)
        

    if all_paths_ok:
      logging.info(sorted(traits.keys()))
      self.traits = traits

    else:
      raise Exception("Missing resources")


  def load_items(self, csv_path):
    row = -1
    loaded_items = {}
    with open(csv_path) as csv_fd:
      reader = csv.DictReader(csv_fd)
      for item in reader:
        row += 1
        if self.is_item_valid(item, True):
          key = tuple(sorted(item.items()))
          if key not in loaded_items:
            loaded_items[key] = item

        else:
          logging.warning(f"Row {row} is not valid")
          self.current_item = item
          raise Exception(item)

    self.current_item = None
    logging.info("{0} items loaded successfully".format(len(loaded_items)))
    return loaded_items


  def load_traits(self):
    traits = {}
    all_paths_ok = True

    # TODO: is path rooted?
    traits_path = os.path.join(self.base_path, "traits.csv")
    with open(path) as fd:
      i = 0
      reader = csv.DictReader(fd)
      for row in reader:
        i += 1

        try:
          row['is_metadata'] = bool(int(row['is_metadata']))
        except KeyError:
          raise NotImplementedError(f"Row {i}: Each CSV item must provide the 'is_metadata' attribute")
        except ValueError:
          row['is_metadata'] = False
          

        try:
          row['z'] = int(row['z'])
        except KeyError:
          raise NotImplementedError(f"Row {i}: Each CSV item must provide the 'z' attribute")
        except ValueError:
          raise NotImplementedError(f"Row {i}: Each CSV item must provide a numeric 'z' attribute")


        try:
          row['mils'] = int(row['mils'])
        except KeyError:
          row['mils'] = 0
          logging.warning(f"Row {i}: setting empty/missing mils to 0")
          #raise NotImplementedError("Each CSV item must provide the 'mils' attribute")


        # fix the paths
        if row['path']:
          slices = row['path'].split('/')
          if len(slices) == 1:
            slices = row['path'].split('\\')

          row['path'] = os.path.join(self.layers_path, *slices)
          if row['path'] and not os.path.exists(row['path']):
            all_paths_ok = False
            logging.error(row['path'])


        # enforce uniqueness
        if row['feature'] in traits:
          if row['expression'] in traits[row['feature']]:
            raise Exception("Row {2}: Duplicate feature-expression: '{0}' '{1}'".format(row['feature'], row['expression'], i))

          else:
            traits[row['feature']][row['expression']] = row

        else:
          traits[row['feature']] = {
            row['expression']: row
          }

        #logging.info(row)
        

    if all_paths_ok:
      logging.info(sorted(traits.keys()))
      self.traits = traits

    else:
      raise Exception("Missing resources")


  def process_links(self, item):
    modified = False
    source = item.copy()
    for key, value in source.items():
      while key:
        trait = self.get_trait(key, value)
        key = trait['link:feature']
        if key:
          if trait['link:expression'] == '*':
            value = self.randomize_trait(key)
          else:
            value = trait['link:expression']

          #logging.info('{0} :: {1}'.format(key, value))
          item[key] = value
          modified = True

        else:
          break

    return modified


  def randomize(self):
    i = 0
    quantity = self.QUANTITY
    if self.continue_items:
      i += len(self.continue_items) - 1
      quantity -= len(self.continue_items)


    new_items = {}
    if self.recipe_items:
      new_items.update(self.recipe_items)
      quantity -= len(new_items)

      #break the ref
      self.recipe_items = {}


    duplicate = 0
    invalid = 0
    self.weights, self.populations = self.compile_base_traits()
    while quantity > 0:
      i += 1
      if duplicate > 10000:
        logging.warning(f"Remaining {quantity}")
        raise Exception("Too many duplicate items")

      if invalid > 10000:
        logging.warning(f"Remaining {quantity}")
        raise Exception("Too many invalid items")


      item = {}
      for feature in self.weights.keys():
        selected, = random.choices(self.populations[feature], weights=self.weights[feature])
        item[feature] = selected


      self.randomize_extended_traits(item, i)   
      if self.is_rule_valid(item):
        #TODO: ignore layers
        #key = item.copy()
        #del key['Background']

        key = tuple(sorted(item.items()))
        if key in self.continue_items or key in new_items:
          duplicate += 1

        else:
          quantity -= 1
          new_items[key] = item

      else:
        invalid += 1

    # flatten
    self.continue_items = self.continue_items.values()
    self.new_items = list(new_items.values())
    if self.new_items:
      logging.info("{0} random items".format(len(self.new_items) ))
    else:
      logging.warning("{0} random items".format(len(self.new_items) ))
    
    # extra shuffle
    #new_items = random.sample(new_items, k=len(new_items))

    return self.new_items


  def randomize_extended_traits(self, item, i):
    logging.info("Processing item {0}".format(i))
    self.process_links(item)


  def randomize_last(self):
    pass


  def randomize_trait(self, feature, **kwargs):
    traits = [trait for trait in self.traits[feature].values()]

    if kwargs:
      for key, value in kwargs.items():
        traits = [trait for trait in traits if trait[key] == value]
        if not traits:
          logging.warning(f"No traits found for {feature} :: '{key}'='{value}'")

    if len(traits) > 1:
      return self.randomize_traits(traits)
    elif len(traits) == 1:
      return traits[0]['expression']
    else:
      return ''


  @staticmethod
  def randomize_values(values, weights):
    selected, = random.choices(values, weights=weights)
    return selected


  def randomize_traits(self, traits):
    population = tuple([t['expression'] for t in traits])
    weights = tuple([t['mils'] for t in traits])
    if len(set(weights)) == 1:
      weights = None

    #logging.info(weights)
    #logging.info(population)
    selected, = random.choices(population, weights=weights)
    return selected


  def validate_rule(self, rule):
    #logging.info(rule)

    #check the match
    feature = rule['match']['feature']
    if rule['match']['is_any']:
      self.traits[feature]

    else:
      for expression in rule['match']['expressions']:
        self.get_trait(feature, expression)


    for allowed in rule['allowed']:
      feature = allowed['feature']
      if allowed['is_any']:
        self.traits[feature]

      else:
        for expression in allowed['expressions']:
          self.get_trait(feature, expression)


    for denied in rule['denied']:
      feature = denied['feature']
      if denied['is_any']:
        self.traits[feature]

      else:
        for expression in denied['expressions']:
          self.get_trait(feature, expression)


  def validate_rules(self):
    if not self.rules:
      # TODO
      rules_path = os.path.join(self.base_path, 'rules.json')
      with open(rules_path) as fd:
        self.rules = json.load(fd)

      for rule in self.rules:
        if rule['type'] == 'conflict':
          if 'is_enabled' in rule:
            if rule['is_enabled']:
              self.validate_rule(rule)
          else:
            self.validate_rule(rule)



class Interruptible(object):
  def __exit__(self, exc_type, exc_val, exc_tb):
    self.stop()


  def __init__(self):
    self.is_running = True
    self.stop_event = threading.Event()


  def register_interrupts(self):
    if hasattr(signal, 'SIGBREAK'):
      # Windows: Ctrl + Break (Pause)
      signal.signal(signal.SIGBREAK, self.signal_interrupt)

    # Linux: Ctrl + C
    signal.signal(signal.SIGINT, self.signal_interrupt)


  # our server listens for "interrupt" CTRL + C
  def signal_interrupt(self, sig, frame):
    if sig == signal.SIGINT:
      logging.warning('Received: signal.SIGINT({})'.format(sig))
      self.stop()

    elif sig == signal.SIGBREAK:
      logging.warning('Received: signal.SIGBREAK({})'.format(sig))
      self.stop()    

    else:
      logging.warning('Unsupported signal: {}'.format(sig))


  def stop(self):
    if not self.stop_event.is_set():
      self.stop_event.set()
      self.is_running = False



class ImageMaker(Interruptible, TraitManager):
  def __exit__(self, exc_type, exc_val, exc_tb):
    TraitManager.__exit__(self, exc_type, exc_val, exc_tb)
    Interruptible.__exit__(self, exc_type, exc_val, exc_tb)


  def __init__(self):
    Interruptible.__init__(self)
    TraitManager.__init__(self)    
    
    self.current_trait = None
    self.queue = Queue()
    self.threads = []
    
    self.layers_path = os.path.join(__dir__, '1-layers')
    self.images_path = os.path.join(__dir__, '2-images')


  def generate_image(self, item):
    self.current_item = item

     # default - combine without shadows
    if True:
      # TODO: if file exists
      # - load
      # - dimensions
      # - check exif :: trait hash?
      composite = self.generate_layer(item)

    # advanced - create partial layers, apply shadows, then composite
    else:
      '''
      bg = {
        'Background': item['Background'],
        'Logo': item['Logo']
      }
      layer1 = self.generate_layer(bg)

      logo = {
        'Logo': item['Logo']
      }
      layer3 = self.generate_layer(logo)
      layer2 = self.generate_shadow(layer3, (-10, 2))

      body = item.copy()
      body.pop('Background')
      body.pop('Logo')

      layer5 = self.generate_layer(body)
      layer4 = self.generate_shadow(layer5, (-50, 10))


      composite = layer1.copy()
      #composite = Image.alpha_composite(composite, layer2)
      #composite = Image.alpha_composite(composite, layer3)
      composite = Image.alpha_composite(composite, layer4)
      composite = Image.alpha_composite(composite, layer5)
      '''

    save_as = os.path.join(self.images_path, '{0}.png'.format(item['index']))
    composite.save(save_as)
    logging.info("CREATED: Image {0}".format(item['index']))


  def generate_images_procs(self, gen_items):
    # raise NotImplementedError()
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

    test0 = json.dumps(recipe0)

    #mp.set_start_method('spawn')
    queue = mp.JoinableQueue()
    
    
    proc = ImageProcessor(queue)
    proc.start()
    logging.info('... started')

    queue.put(Task(test0))
    queue.join()


    # poison pill
    queue.put(Task.Empty)
    proc.join()
    logging.info('proc joined')
    exit()  
  
  
  def generate_images_threads(self, gen_items):
    # start the background threads
    self.threads = []
    for i in range(self.use_threads):
      t = threading.Thread(target=self.process_image, daemon=False)
      t.start()
      self.threads.append(t)

    # enqueue images to generate
    for item in gen_items:
      self.queue.put(item)

    # stop the background threads
    for t in self.threads:
      self.queue.put(None)

    self.queue.join()


  def generate_items(self):
    # generate metadata
    super().generate_items()

    if self.CREATE_IMAGES:
      gen_items = []
      all_items = [*self.continue_items, *self.new_items]
      for idx in range(self.START_IDX, len(all_items)):
        gen_items.append(all_items[idx])

    
      if self.use_procs:
        self.generate_images_procs(gen_items)

      elif self.use_threads:
        self.generate_images_threads(gen_items)

      else:
        for item in gen_items:
          if self.is_running:
            self.generate_image(item)
          else:
            break


  def generate_layer(self, item):
    layers = {}
    for feature, expression in item.items():
      self.current_trait = None
      if feature != 'index':
        self.current_trait = current_trait = self.get_trait(feature, expression)

        if current_trait['path']:
          layers[current_trait['z']] = self.get_image(current_trait)
        elif expression and current_trait['z'] > 0:
          logging.warning(f"{feature}: {expression} does not have a path"  )

    self.current_trait = None


    composite = None
    indices = sorted(layers.keys())
    for i in indices:
      if i in layers:
        if composite:
          try:
            #logging.debug("Appending layer {0} - {1}: {2}".format(i, layers[i]['feature'], layers[i]['expression']) )
            composite = Image.alpha_composite(composite, layers[i]['image'])

          except Exception as ex:
            logging.error("Composite failed with layer '{0}:{1}'".format(layers[i]['feature'], layers[i]['expression']) )
            raise ex

        else:
          #logging.debug("Base layer {0} - {1}: {2}".format(i, layers[i]['feature'], layers[i]['expression']) )
          composite = layers[i]['image'].copy()

        if self.LOW_MEM:
          layers[i]['image'].close()

      else:
        #logging.debug("Omit layer {0}".format(i))
        pass


    return composite


  def generate_shadow(self, layer, translation):
    shadow = Image.new('RGBA', layer.size)
    shadow.paste('#33333380', None, layer)
    shadow = shadow.rotate(0, PIL.Image.BICUBIC, 0, None, translation)
    return shadow


  def get_image(self, trait):
    if self.LOW_MEM:
      trait = trait.copy()
      logging.info("LOAD:  Image '{0}'".format(trait['path']) )
      trait['image'] = Image.open(trait['path']).convert('RGBA')
      if self.RESIZE:
        trait['image'] = trait['image'].resize(self.RESIZE)

      return trait

    else:
      try:
        image = trait['image']
        logging.debug("CACHE: Use image '{0}'".format(trait['path']) )
        return trait

      except KeyError:
        logging.info("LOAD:  Image '{0}'".format(trait['path']) )
        trait['image'] = Image.open(trait['path']).convert('RGBA')
        if self.RESIZE:
          trait['image'] = trait['image'].resize(self.RESIZE)
        
        return trait


  def init(self):
    self.layers_path = os.path.join(self.base_path, '1-layers')

    try:
      self.images_path = os.path.join(self.base_path, '2-images')
      os.mkdir(self.images_path)
    except FileExistsError:
      pass

    TraitManager.init(self)


  def process_image(self):
    while not self.stop_event.is_set():
      try:
        item = self.queue.get()
        if item is None:
          self.queue.task_done()
          break

        else:
          self.generate_image(item)
          self.queue.task_done()

      except Exception as ex:
        logging.exception(ex)
        self.queue.task_done()
