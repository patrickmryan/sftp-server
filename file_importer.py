import re, sys, boto3, argparse, pdb



class FileRetriever():
    def __init__(self, scheme=None, path=None):
        self.scheme = scheme
        self.path = path

    def __str__(self):
        return f'{self.__class__} scheme={self.scheme} path={self.path}'

    @staticmethod
    def retrieverClass(address):
        matched = re.match(r'^(?P<scheme>[^/:]+)://(?P<path>.*)$', address)

        if (not matched):   # no scheme implies this is a local file
            scheme = 'file'
            path = address
        else:
            scheme = matched.group('scheme')
            path = matched.group('path')

        if (scheme == 'file'):
            return LocalFile(scheme=scheme, path=path)
        if (scheme == 's3'):
            return AwsS3File(scheme=scheme, path=path)
        if (scheme == 'http' or scheme == 'https'):
            return HttpFile(scheme=scheme, path=path)

        # if we got here, there's a scheme but I dont recognize it
        raise Exception(f'{address}: no parser for scheme {scheme}')

    def retrieveContent(self):
        pass

class LocalFile(FileRetriever):
    pass

class AwsS3File(FileRetriever):
    pass

class HttpFile(FileRetriever):
    pass



if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--file', dest='file', required=True)
    args = parser.parse_args()

    retriever = FileRetriever.retrieverClass(args.file)
    print(retriever)

    # main(directory=args.directory, git_only=args.git_only, dryrun=args.dryrun)
