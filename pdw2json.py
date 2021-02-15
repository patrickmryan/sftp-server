import sys, argparse, re, datetime
import json
import pdb
from struct import *
from collections import namedtuple

parser = argparse.ArgumentParser()
parser.add_argument('--pdw-file', dest='pdw_file', required=True)
parser.add_argument('--json-file', dest='json_file', default=None, required=False)
args = parser.parse_args()

pdw_filename = args.pdw_file
json_filename = args.json_file

# https://docs.python.org/3.8/library/struct.html

# (U) The PDW fileraw_data interface is a file format definition. The convention for PDW file
# is of the form: SS_YYYYMMDD_HHMMSS_NNNNNNNNNN_SSSSSSSSSSSSSSSSSSSS.pdw, naming
#
# where:
# (U) SS is a numeric identifier that can identify the collection site (0-99)
# (U) YYYYMMDD is the UTC date of the first sample in the file
# (U) HHMMSS is the UTC time of the first sample in the file (24 hour format)
# (U) NNNNNNNNNN is nanoseconds after the second for the first sample in the file
# (U) ssssssssssssssssssss is a unique 64-bit integer
# Table 18: (U) Platinum Data Formats Name Description

type_mapping = {
    'SA': '',  # SA Scalar ASCII data
    'SB': 'h', # SB Scalar signed 8-bit integer
    'SD': 'd', # SD Scalar 64-bit floating point value
    'SF': 'f', # SF Scalar 32-bit floating point value
    'SI': 'h', # SI Scalar signed 16-bit integer
    'SL': 'i', # SL Scalar signed 32-bit integer
    'SO': 'q', # SO Scalar Excess-128 8-bit signed integer sometimes referred to as an offset byte
    'SU': 'H', # SU Scalar unsigned 16 -bit integer
    'SV': 'I', # SV Scalar unsigned 32-bit integer
    'SX': 'q'  # SX Scalar signed 64-bit integer
}

sources = {
    '00' : '',
    '01' : 'Soi1', # /Soi2 also uses 01?
    '02' : 'Soi3' ,
    '03' : 'Soi4' ,
    '04' : 'Soi5'
}

# prefix of ANT ?
header_format= [
    ('TOA',            'SX'),
    ('PF',             'SD'),
    ('PW',             'SF'),
    ('PA',             'SF'),
    ('SNR',            'SF'),
    ('MOD_TYPE',       'SB'),
    ('AOA_TYPE',       'SB'),
    ('CHANNEL',        'SB'),
    ('MOD_PARAMETER',  'SF'),
    ('AOA',            'SF'),
    ('FLAGS',          'SI'),
    ('DEINT_ID',       'SI'),
    ('PHASE',          'SF'),
    ('PHASE_REF_TIME', 'SD'),
    ('TOA_DEV',        'SF'),
    ('PF_DEV',         'SF')
]

# struct_format = '='+''.join(tuple[1] for tuple in header_format)
# header_record = namedtuple('pdw_header', (' '.join(tuple[0] for tuple in header_format)))

pdw_file = open(pdw_filename, "rb")
raw_data = pdw_file.read(64)

header_record._make(unpack(struct_format, raw_data))
print(header_record)

pdw_file.close()
