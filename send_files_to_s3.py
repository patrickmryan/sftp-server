#
#
#

import boto3
import inotify.adapters
import time
import urllib, argparse, sys, re
import os
import os.path

# https://pypi.org/project/inotify/

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
parser.add_argument('--suffix', dest='suffix', required=False, default='')
parser.add_argument('--delete-after-upload', action='store_true', default=False)
parser.add_argument('--verbose', action='store_true', default=False)

args = parser.parse_args()

root_directory = args.directory
s3bucket = args.s3bucket
s3prefix = args.s3prefix
suffix = args.suffix
delete_after_upload = args.delete_after_upload
verbose = args.verbose

logger = VerboseLogger() if verbose else SilentLogger()
# inotifywait --monitor --recursive --quiet --event close_write $PWD/out

s3_client = boto3.client('s3')

if (suffix): # filter to only files with a matching suffix
    pattern = f'.*{suffix}$'  # pattern for file suffix
else:
    pattern = '.*'            # match everything
filter = re.compile(pattern, flags=re.IGNORECASE)

listener = inotify.adapters.InotifyTree(root_directory)
# listener.add_watch(directory)

new_directory_event = set(['IN_CREATE', 'IN_ISDIR'])

for event in listener.event_gen(yield_nones=False):
    (_, type_names, path, filename) = event

    # print(f"PATH=[{path}] FILENAME=[{filename}] EVENT_TYPES={type_names}")

    if (set(type_names) == new_directory_event):
        # print('new directory, need to pause')
        time.sleep(2)  # wait a bit
        continue

    if (not ('IN_CLOSE_WRITE' in type_names)):
        continue   # we only care about IN_CLOSE_WRITE events

    if (not filter.match(filename)):
        logger.log(f'ignoring {filename}')
        continue

    # print(f"PATH=[{path}] FILENAME=[{filename}]")
    absolute_path = os.path.normpath(f'{path}/{filename}')

    key=os.path.relpath(absolute_path, start=root_directory)
    if (s3prefix):
        key = f'{s3prefix}/{key}'
    key = os.path.normpath(key)  # remove any redundant characters

    tags = {
        "filename" : absolute_path
        # hostname?
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

        response = s3_client.put_object(Bucket=s3bucket,
                                        Key=key,
                                        Body=open(absolute_path, "rb"),
                                        Tagging=tagging)

        # will only get here if put_object succeeded
        uploaded=True
        # logger.log(response)

    except s3_client.exceptions.NoSuchBucket as e:
        logger.log(e)
        logger.log(f"ignoring {filename}, no bucket named {event['destination']}")
        continue
    except Exception as e:
        logger.log(f'put_object failed with exception {e}')
        continue

    # We got here if the s3 put_object worked.

    if (uploaded and delete_after_upload):
        os.remove(absolute_path)
        logger.log(f'deleted {absolute_path}')
