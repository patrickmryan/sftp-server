#
#
# python3 file_importer.py --uri s3://pmryan-galactica-code/vault-s3-policy.json

import re, sys, argparse
import boto3
import urllib3, ssl
import pdb


class FileRetriever():
    def __init__(self, scheme=None, path=None):
        self.scheme = scheme
        self.path = path

    def __str__(self):
        return f'{self.__class__} {self.scheme}://{self.path}'

    def retrieveContent(self):
        pass

    @staticmethod
    def schemes():
        return []

    @staticmethod
    def retrieverFor(address):
        # https://tools.ietf.org/html/rfc3986#section-3.1

        matched = re.match(r'^(?P<scheme>[A-Za-z][\w+-.]*)://(?P<path>.*)$', address)

        if (matched):
            scheme = matched.group('scheme').lower()
            path = matched.group('path')

        else:  # no scheme implies this is a local file
            scheme = 'file'
            path = address

        # Traverse the subclasses. See which one will handle this URL scheme
        retriever_class = next((_class for _class in FileRetriever.__subclasses__()
                                if (scheme in _class.schemes())), None)

        if (not retriever_class):
            # if we got here, there's a scheme but I don't recognize it
            raise Exception(f'{address}: no parser for scheme {scheme}')

        # Return an instance of the class that will handle an address of the specified scheme.
        return retriever_class(scheme=scheme, path=path)


class LocalFile(FileRetriever):
    @staticmethod
    def schemes():
        return [ 'file' ]

    def retrieveContent(self):
        fp = open(self.path,'r')
        content = fp.read()
        fp.close()
        return content

class AwsS3File(FileRetriever):
    @staticmethod
    def schemes():
        return [ 's3' ]

    def retrieveContent(self):
        s3_client = boto3.client('s3')

        elements = self.path.split('/')  # self.path will be of the form "bucket/this/is/key.txt"
        bucket = elements[0]             # bucket name is the first element of the path
        key = '/'.join(elements[1:])     # key is everything else

        try:
            response = s3_client.get_object(Bucket=bucket, Key=key)
            bytes = response['Body'].read()
            return bytes.decode()

        except s3_client.exceptions.NoSuchBucket as e:
            print(f'{bucket}: could not access bucket - {e}')
            raise

        except s3_client.exceptions.NoSuchKey as e:
            print(f'{key}: could not find in {bucket} - {e}')
            raise

class HttpFile(FileRetriever):
    @staticmethod
    def schemes():
        return [ 'http', 'https' ]

    def retrieveContent(self):

        urllib3.disable_warnings()
        http = urllib3.PoolManager(cert_reqs = ssl.CERT_NONE)
        url = f'{self.scheme}://{self.path}'
        response = http.request('GET', url)  # headers=...

        return response.data.decode()   #'utf-8'


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--uri', dest='uri', required=True)
    args = parser.parse_args()

    retriever = FileRetriever.retrieverFor(args.uri)
    print(retriever.retrieveContent())
