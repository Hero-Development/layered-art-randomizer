#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging, logging.handlers, os, sys

from PIL import Image
from psd_tools import PSDImage

__dir__ = os.path.realpath( os.path.dirname( __file__ ) )
os.chdir( __dir__ )


def get_parent_names(layer):
  names = [layer.name]
  while layer.parent:
    layer = layer.parent
    names.insert(0, layer.name)

  return names


def extract_layers(to_path, parent_layer):
  if not os.path.isdir(to_path):
    print("create path: %s" % to_path)
    os.mkdir(to_path)


  for layer in parent_layer:
    layer_name = layer.name
    names = get_parent_names(layer);

    pil = layer.topil()
    if pil:
      # export
      image_path = os.path.join(to_path, layer_name) +'.png'
      if os.path.isfile(image_path):
        print("EXISTS '%s.png'" % '/'.join(names))
        # print(layer.bbox)
        # print(layer.offset)
        # print(pil.getbbox())

      else:
        # try:
        #   print("SAVE '%s.png'" % '/'.join(names))
        #   pil.save(image_path)
        # except UnicodeEncodeError:
        #   names[-1] = names[-1].decode('ascii', '
        print(("SAVE '%s.png'" % '/'.join(names)).encode('utf-8'))
        canvas = Image.new("RGBA", (6300, 6300))
        canvas.putalpha(0)
        canvas.paste(pil, layer.offset)
        canvas.save(image_path)
        canvas.close()

    else:
      # recurse
      print('---== %s ==---' % '/'.join(names))
      new_path = os.path.join(to_path, layer_name)
      extract_layers(new_path, layer)


layers_path = os.path.join(__dir__, '1-layers')
psd = PSDImage.open('chimerapillar_master280_final03.psd')
extract_layers(layers_path, psd)
