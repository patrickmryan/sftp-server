import sys, argparse, re, datetime
import json
import pdb
from struct import *
from collections import namedtuple

def b2s(string_bytes):
    string = string_bytes.decode('utf-8')  # convert bytes to a string
    last=next((i for i in range(len(string)-1,0,-1) if string[i] != '\0'), -1) # find the last non-null char
    return string[0:last+1]  # return the substring

data_fields = [
    ( 'sensor'        , '8s'),   # 8
    ( 'reading_one'   , 'I'),    # 4
    ( 'reading_two'   , 'l'),    # 4
    ( 'reading_three' , 'f'),    # 4
    ( 'reading_four'  , 'd')     # 8
]

format_string = '='+''.join( [ tuple[1] for tuple in data_fields ] )



Data_record = namedtuple('fields', (' '.join(tuple[0] for tuple in data_fields)))

data_file = open('sample1.binary','rb')

raw_data = data_file.read(28)

rec = Data_record._make(unpack(format_string, raw_data))
# strings will be null-filled
print(f'sensor = {b2s(rec.sensor)}')
print(rec)
