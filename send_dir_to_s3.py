import boto3
import json
import os, sys, argparse

class Logger:
    def __init__(self, target=None, prefix=''):
        self.prefix=prefix
        pass

    def log(message):
        pass # do nothing

class SilentLogger(Logger):
    def log(self, message):
        pass # do nothing

class VerboseLogger(Logger):
    def log(self, message):
        print(f'{self.prefix}{message}')


# logger
# use with verbose
# two subclasses.  quiet and noisy


parser = argparse.ArgumentParser()
parser.add_argument('--source-directory', dest='source_directory', required=True)
# filename suffix pattern for limiting?
parser.add_argument('--s3bucket', dest='s3bucket', required=True)
parser.add_argument('--s3prefix', dest='s3prefix', required=False, default='')
parser.add_argument('--delete-after-upload', action='store_true', default=False)
parser.add_argument('--verbose', action='store_true', default=False)

args = parser.parse_args()

source_directory = args.source_directory
s3bucket = args.s3bucket
s3prefix = args.s3prefix
delete_after_upload = args.delete_after_upload
verbose = args.verbose

logger = VerboseLogger() if verbose else SilentLogger()

logger.log(args)

# https://www.newbedev.com/python/howto/how-to-iterate-over-files-in-a-given-directory/
for entry in os.scandir(source_directory):
    filename = entry.path
    logger.log(filename)


# s3 client
# source directory
# delete-after-transfer flag
# s3 bucket
# s3 prefix
