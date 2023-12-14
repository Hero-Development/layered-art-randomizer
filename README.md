# Squeebo's Layered Art Randomizer


## Prerequisites

  - Install python 3.x
  - Use `pip` to install `pillow`:<br />
  ```pip install pillow```


## Setup
The primary requirement for using these scripts is to unpack and organize files into some folder.  Because I'm anal, that folder is usually `1-layers`.  In this folder, you should organize things into unique areas of the PFP.  For example:
```
1-Backgrounds
2-Skin (or 2-Body)
3-Clothes
4-Mask
5-Hair
6-Hat
7-Accessory
```

This is optional, but will help `1-loader.py` group things more intelligently.  Manually editing the `feature` values in step 1 will also create groups.

Sometimes art goes through a few revisions, and I don't want to be the guy that lost the art.  Because of this, I usually make another folder called `0-sources` which holds "raw" layers.  After each round of art is loaded, I use [Beyond Compare](https://www.scootersoftware.com/) to identify which layers have changed.  With the sources and layers organized, it's easier to adapt to unruly art projects.


## 1. loader.py
usage: `python 1-loader.py path/to/layers`

`path/to/layers` - Indicate where the layers are organized.  If you followed the `Setup`, this value should be `1-layers`

This tool will load all of the files it finds into "traits.csv" with the following columns:
  - **z** the height of the layer;  lower = further back, higher = toward the front
  - **feature:**  the grouping name (key) that will be tracked in the python code
  - **expression:**  the grouping value that will be tracked in the python code
  - **mils:**  defaults to 1;  an integer relative value to control randomization
  - **link:feature"**  advanced;  use with `link:expression` to link the current layer to another
  - **link:expression:**  advanced;  use with `link:feature` to link the current layer to another
  - **is_metadata:** defaults to 1 (yes);  allows you to toggle this layer from creating metadata
  - **display_type:** defaults to "string"; allows this trait to use other display types in the [Metadata Standards](https://docs.opensea.io/docs/metadata-standards)
  - **trait_type:** the trait type within JSON metadata
  - **value:** the trait value within JSON metadata;  title casing will be applied
  - **path:**  the relative path to the image/resource
  - **display_type:** defaults to "string";  used for distinct OpenSea attribute types

See `samples/traits.csv` for an example


After you have applied some organization to `traits.csv`, move on to step 2 and see what you've created.


## 2. generator.py
usage: `python 2-generator.py`

Execute this file next to "traits.csv" to perform several generative actions:
1. Load all of "traits.csv" into memory including extra columns.
To use extra columns, they must have a column header.
2. Generate `TraitGenerator.QUANTITY` unique combinations according to the `mils` values
3. Generate images and JSONs matching the items created in #2

### Configuration
  - **TraitGenerator.BASE_TRAITS:** Indicates which `feature` (keys) are used for randomization
  - **TraitGenerator.LOW_MEM:** Turned off layer caching.  Generator will be slower, but won't crash from running out of memory
  - **TraitGenerator.METADATA_FORMAT:**  Provides templated data for the `name`, `description`, and `image` of the metadata
  - **TraitGenerator.QUANTITY:** The quantity of unique combinations to generate
  - **TraitGenerator.RESIZE:** If this is a 2-tuple, resizes the layers to these dimensions to expedite processing



### Troubleshooting

  - `KeyError: 'Overlay Top Most Layer'`
  <br />If you receive this error, it means the script cannot find the `feature` that you specified in `BASE_TRAITS`.  Check the the script and CSV for spaces, tabs, or non-ascii characters.