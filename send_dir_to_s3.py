import boto3
import json
import os, sys
import urllib, argparse

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

# create as an array because we will be deleting as we go along
filenames_iter = [ entry.name for entry in os.scandir(source_directory) ]
filenames = [*filenames_iter]

if (not filenames):   # nothing to do
    logger.log(f'no files in {source_directory}')
    sys.exit(0)

s3_client = boto3.client('s3')

# https://www.newbedev.com/python/howto/how-to-iterate-over-files-in-a-given-directory/
for filename in filenames:
    # filename = entry.name
    logger.log(filename)

    path = filename.split('/')
    key = filename
    if (s3prefix):
        key = f'{s3prefix}/{key}'
    absolute_path = f'{source_directory}/{filename}'

    tags = {
        "filename" : absolute_path
        # "groupName" : groupName,
        # "streamName" : streamName,
        # "fromTime" : fromTime.isoformat(),
        # "toTime" : toTime.isoformat(),
        # "format" : "syslog gzipped"
    }

    tagging = urllib.parse.urlencode(tags)

    try:
        logger.log(f'uploading s3://{s3bucket}/{key}')
        response = s3_client.put_object(Bucket=s3bucket,
                                        Key=key,
                                        Body=open(absolute_path, "rb"),
                                        Tagging=tagging)

        # will only get here if put_object succeeded
        logger.log(response)
        if (delete_after_upload):
            os.remove(absolute_path)
            logger.log(f'deleted {absolute_path}')

    except s3_client.exceptions.NoSuchBucket as e:
        print(e)
        print('no bucket named ' + event['destination'])
        # pass



# s3 client
# source directory
# delete-after-transfer flag
# s3 bucket
# s3 prefix
