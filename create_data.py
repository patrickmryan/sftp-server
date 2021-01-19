import sys, argparse, re, datetime
import json
import pdb
from struct import *
from collections import namedtuple

# https://docs.python.org/3.8/library/struct.html

data_format = [
    ( 'sensor'        , '8s' ),   # 8
    ( 'reading_one'   , 'I' ),    # 4
    ( 'reading_two'   , 'l' ),    # 4
    ( 'reading_three' , 'f')      # 4
]

sample1 = {
    'sensor' : b'xyz001',
    'reading_one' : 8192,
    'reading_two':  32768,    # 1000000002
    'reading_three' : 2021.011905
}

format_string = '='+''.join( [ tuple[1] for tuple in data_format ] )
packed_data = pack(format_string, sample1['sensor'], sample1['reading_one'], sample1['reading_two'], sample1['reading_three'])

f = open('sample1.binary','wb')
f.write(packed_data)
