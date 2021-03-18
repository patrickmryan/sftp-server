import sys
from datetime import datetime, timezone
import boto3
import json
import re
import urllib3, ssl
import argparse
from botocore.exceptions import ClientError

# This script implements the API and behavior detailed in the page below:
#
# https://www.rsyslog.com/doc/v8-stable/configuration/modules/omprog.html
#
# This code makes use of the "jsonmesg" property available in an rsyslog template.
#
# https://www.rsyslog.com/doc/v8-stable/configuration/properties.html
#
# The code is designed to accept one complete JSON structure per line from stdin. The template
# That sends data to this process should include only "%jsonmesg\n".
#

class Logger:
    def __init__(self, stream):
        self.debug_file = stream

    def log(self, message):
        if (self.debug_file):
            self.debug_file.write(message)
            self.debug_file.flush()
        return
    def write(self, message):
        return self.log(message)
    def close(self):
        if (self.debug_file()):
            self.debug_file.close()
        return

class AwsMetadata:
    def __init__(self):
        self.http = urllib3.PoolManager(cert_reqs = ssl.CERT_NONE)

    def api_root(self):
        return "169.254.169.254/latest/meta-data/"

    def url_for_api(self, api):
        # This code will tolerate redundant slashes and return a clean, well-formed URL

        path = self.api_root() + '/' + api
        path = re.sub('/+','/', path) # get rid of redudant slashes.
        path = re.sub('^/','', path) # if there's a leading slash, whack it

        return f"http://{path}"

    def get(self, path):
        # example:   metadata.get("placement/availability-zone")

        response = self.http.request('GET', self.url_for_api(path))
        return response.data.decode()


class CwForwarder:
    def __init__(self, logGroupName=None, logStreamName=None, region=None, logger=None):
        self.logGroupName=logGroupName
        self.logStreamName=logStreamName
        self.logger=logger
        self.client = boto3.client('logs', region_name=region)


    def nextSequenceToken(self, logStreamForEvent):

        response = self.client.describe_log_streams(
            logGroupName=self.logGroupName,
            logStreamNamePrefix=logStreamForEvent)

        log_streams = response.get('logStreams', None)

        if (not log_streams):  # stream not created yet
            response = self.client.create_log_stream(
                logGroupName=self.logGroupName,
                logStreamName=logStreamForEvent)
            return '0'

        stream_info = log_streams[0]
        return stream_info.get('uploadSequenceToken', '0')

    def forwardSyslogToCloudWatch(self):

        # compiled regex to remove extraneous whitespace
        no_whitespace = re.compile('^\s*(\S.*\S)\s*$')

        for line in sys.stdin:
            logger.write(line)

            json_message = line.rstrip()

            if (not json_message):  # really should not happen
                logger.write("message is blank\n")
                sys.stdout.write("OK\n")
                continue

            # If JSON parse fails, just dump the raw text to cloudwatch.

            parsed = None
            try:
                parsed = json.loads(json_message)
            except json.JSONDecodeError as err:
                logger.write(f'JSON parse error: {err}')

            logStreamForEvent = 'default'
            if (parsed):
                if ("fromhost" in parsed):
                    logStreamForEvent=parsed["fromhost"]

                timestamp_string = parsed['timereported']

                try:
                    # https://docs.python.org/3/library/datetime.html#datetime.datetime.fromisoformat
                    event_timestamp = datetime.fromisoformat(timestamp_string)
                    #logger.write(timestamp_string + ' -> ' + event_timestamp.isoformat())

                except ValueError as err:
                    # Could not parse the timestamp. As a last resort, get the current time.
                    logger.write(f'could not parse date string "{timestamp_string}", defaulting to current time\n')
                    event_timestamp = datetime.now(timezone.utc)

                # convert to milliseconds
                epoch_ms = int((event_timestamp.timestamp())*1000.0)

                # using rawmsg instead of msg
                result = no_whitespace.match(parsed['rawmsg'])  # remove leading and trailing whitespace
                # rawmsg might be blank. have to send something as put_log_events will
                # fail if the message is zero length

                if (result):
                    message = result.group(1)
                else:
                    # got a blank message, which is weird.
                    # convey info about what host sent the blank messsage
                    message = 'blank message'

                    clues = ["fromhost", "fromhost-ip"]
                    for key in list(filter(lambda key: (key in parsed), clues)):
                        message = message + f', {key}={parsed[key]}'

            else: # JSON parsing failed. construct a message to be passed
                message = json_message
                event_timestamp = datetime.now(timezone.utc)
                epoch_ms = int((event_timestamp.timestamp())*1000.0)

            try:
                # send the syslog event to CloudWatch
                logger.write(f'about to send message to {self.logGroupName}/{logStreamForEvent} - "{message}"')
                token = self.nextSequenceToken(logStreamForEvent)
                response = client.put_log_events(
                                logGroupName=self.logGroupName,
                                logStreamName=logStreamForEvent,
                                logEvents = [ { 'timestamp' : epoch_ms, 'message' : message } ],
                                sequenceToken = token)

                # 'tooNewLogEventStartIndex'
                # 'tooOldLogEventEndIndex':
                # 'expiredLogEventEndIndex'

                if ('rejectedLogEventsInfo' in response):
                    logger.write(f"failed sending event: {json_message}\n")
                    logger.write('rejectedLogEventsInfo\n')
                    for key, value in (response['rejectedLogEventsInfo']).items():
                        logger.write(f'  {key} -> {value}\n')

                else:  # no error when sending event

                    # To confirm a message, the program must write a line with the word OK to its standard output.
                    # If it writes a line containing anything else, rsyslog considers that the message could not be
                    # processed, keeps it in the action queue, and re-sends it to the program later
                    # (after the period specified by the action.resumeInterval parameter).

                    sys.stdout.write("OK\n")

            # except UnrecognizedClientException as err:
            #     logger.write(f'UnrecognizedClientException: {err}')
            #     logger.write('  might be bad access credentials')

            except ClientError as err:
                # Need to cleanly handle failure to send message

                logger.write(f"ERROR sending message to cloudwatch - {err}\n")
                sys.stderr.write(f"ERROR: {err}\n")

# main program
if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    # https://docs.python.org/3/library/argparse.html

    parser.add_argument("--log-stream", help="name of CloudWatch log stream",
                        dest="log_stream", required=True)
    parser.add_argument("--log-group", help="name of CloudWatch log group",
                        dest="log_group", required=True)
    parser.add_argument("--debug-file", help="file name for debug output",
                        dest="debug_file", required=False, default=None)

    # handle command line args
    args = parser.parse_args()

    if (args.debug_file):
        logger = Logger(open(args.debug_file, "a"))
    else:
        logger = Logger(None)

    # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/
    #   logs.html#CloudWatchLogs.Client.put_log_events

    # first check for presence of $AWS_DEFAULT_REGION

    metadata = AwsMetadata()

    # grab the instance metadata so that we figure out what region we're in
    az = metadata.get("placement/availability-zone")
    result = re.match('^(\S+-\d)[a-z]$', az)   # extract the region name from the AZ name
    region = result.group(1)
    client = boto3.client('logs', region_name=region)



    cw_forwarder = CwForwarder(
                        logGroupName=args.log_group,
                        logStreamName=args.log_stream,
                        region=region,
                        logger=logger)

    cw_forwarder.forwardSyslogToCloudWatch()
