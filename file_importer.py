#
#
#

import re, sys, boto3, argparse, urllib3, pdb


class FileRetriever():
    def __init__(self, scheme=None, path=None):
        self.scheme = scheme
        self.path = path

    def __str__(self):
        return f'{self.__class__} scheme={self.scheme} path={self.path}'

    @staticmethod
    def retrieverFor(address):
        # https://tools.ietf.org/html/rfc3986#section-3.1

        # matched = re.match(r'^(?P<scheme>[^/:]+)://(?P<path>.*)$', address)
        matched = re.match(r'^(?P<scheme>[A-Za-z][\w+-.]*)://(?P<path>.*)$', address)

        if (not matched):   # no scheme implies this is a local file
            scheme = 'file'
            path = address
        else:
            scheme = matched.group('scheme').lower()
            path = matched.group('path')

        _class = None

        # iterate over FileRetriever.__subclasses__()

        if (scheme == 'file'):
            _class = LocalFile
        if (scheme == 's3'):
            _class = AwsS3File
        if (scheme == 'http' or scheme == 'https'):
            _class = HttpFile

        if (_class):
            return _class(scheme=scheme, path=path)

        # if we got here, there's a scheme but I dont recognize it
        raise Exception(f'{address}: no parser for scheme {scheme}')

    def retrieveContent(self):
        pass

class LocalFile(FileRetriever):
    def retrieveContent(self):
        fp = open(self.path,'r')
        content = fp.read()
        fp.close()
        return content

class AwsS3File(FileRetriever):
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
    def retrieveContent(self):
        pass


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--file', dest='file', required=True)
    args = parser.parse_args()

    retriever = FileRetriever.retrieverFor(args.file)

    print(f'content of {args.file}')
    print(retriever.retrieveContent())
