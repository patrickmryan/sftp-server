import boto3
import inotify.adapters
import subprocess
import argparse, sys, re

# https://pypi.org/project/inotify/

# args
#   --directory
#   --s3bucket
#   --delete-after-upload

class Logger:
    def __init__(self, target=None, prefix=''):
        self.prefix=prefix
        pass

    def log(self, message):
        pass # do nothing

class SilentLogger(Logger):
    def log(self, message):
        pass # do nothing

class VerboseLogger(Logger):
    def log(self, message):
        print(f'{self.prefix}{message}')


parser = argparse.ArgumentParser()
parser.add_argument('--directory', dest='directory', required=True)
parser.add_argument('--s3bucket', dest='s3bucket', required=True)
parser.add_argument('--s3prefix', dest='s3prefix', required=False, default='')
parser.add_argument('--delete-after-upload', action='store_true', default=False)
parser.add_argument('--verbose', action='store_true', default=False)

args = parser.parse_args()

root_directory = args.directory
s3bucket = args.s3bucket
s3prefix = args.s3prefix
delete_after_upload = args.delete_after_upload
verbose = args.verbose

logger = VerboseLogger() if verbose else SilentLogger()
# inotifywait --monitor --recursive --quiet --event close_write $PWD/out

s3_client = boto3.client('s3')

listener = inotify.adapters.InotifyTree(root_directory)
# listener.add_watch(directory)

for event in listener.event_gen(yield_nones=False):
    (_, type_names, path, filename) = event


    #print(f"PATH=[{path}] FILENAME=[{filename}] EVENT_TYPES={type_names}")
    if (not ('IN_CLOSE_WRITE' in type_names)):
        continue   # we only care about IN_CLOSE_WRITE events

    print(f"PATH=[{path}] FILENAME=[{filename}]")
    absolute_path = os.path.normpath(path+filename)
    key=os.relpath(absolute_path, start=root_directory)
    if (s3prefix):
        key = f'{s3prefix}/{key}'


    tags = {
        "filename" : absolute_path
        # "groupName" : groupName,
        # "streamName" : streamName,
        # "fromTime" : fromTime.isoformat(),
        # "toTime" : toTime.isoformat(),
        # "format" : "syslog gzipped"
    }

    tagging = urllib.parse.urlencode(tags)

    uploaded = False
    try:
        logger.log(f'uploading {absolute_path} to s3://{s3bucket}/{key}')

        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.put_object
        #
        # other params to think about:
        #    StorageClass, ACL, encryption
        #

        # response = s3_client.put_object(Bucket=s3bucket,
        #                                 Key=key,
        #                                 Body=open(absolute_path, "rb"),
        #                                 Tagging=tagging)

        # will only get here if put_object succeeded
        uploaded=True
        logger.log(response)

    except s3_client.exceptions.NoSuchBucket as e:
        print(e)
        print('no bucket named ' + event['destination'])
        # pass

    if (uploaded):
        if (delete_after_upload):
            os.remove(absolute_path)
            logger.log(f'deleted {absolute_path}')
