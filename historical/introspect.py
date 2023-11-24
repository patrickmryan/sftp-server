import urllib3, ssl
from urllib.parse import urlencode
import sys
import re


def retrieve_data(http, url, depth):
    response = http.request("GET", url)
    text = response.data.decode("utf-8")

    # if (re.search('/$', url)):
    if url[-1] == "/":
        # trailing slash means that the return value is an array
        for n in range(1, depth):
            sys.stdout.write(" ")
        print(url)

        paths = re.split("\n", text)
        hash = {}

        for step in paths:
            next_url = url + step
            # https://docs.python.org/3/library/re.html
            result = re.search("(.*)\/$", step)  # if present, whack the trailing slash
            key = result.group(1) if result else step
            hash[key] = retrieve_data(http, next_url, depth + 1)

        return hash

    else:
        for n in range(1, depth):
            sys.stdout.write(" ")
        print(url + " -> " + text)
        return text


urllib3.disable_warnings()
http = urllib3.PoolManager(cert_reqs=ssl.CERT_NONE)

response = retrieve_data(http, "http://169.254.169.254/latest/meta-data/", 0)
