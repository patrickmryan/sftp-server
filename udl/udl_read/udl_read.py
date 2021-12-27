import os
import json
from urllib.parse import urlencode
import urllib3, ssl
import pandas as pd

def lambda_handler(event, context):
    
    token = os.environ.get('CREDENTIAL')
    if not token:
        raise Exception('missing ENV variable CREDENTIAL')
    
    #Pick one of the two following lines to set up your UDL login credentials.
    #   The first option requires an open text username and password.
    #   The second (preferred) option uses the value from the UDL Base64 token
    #   utility (accessed via the Utility page of the UDL Storefront) to
    #   create the encoded string.
    
    # creds = "Basic " + base64.b64encode("username:password").decode("ascii")
    # creds = "Basic aCharacterStringFromUDLutility=="

    headers = {
        'Authorization' : f"Basic {token}"
    }
    
    # urllib3.disable_warnings()
    http = urllib3.PoolManager()  # (cert_reqs=ssl.CERT_NONE)
    
    #Copy the URL from the UDL Dynamic Query Tool into the line below.
    #   This sample query will return all element sets for the International
    #   Space Station (satellite number 25544) generated 11-1-2018 or later.

    # url="https://unifieddatalibrary.com/udl/elset?epoch=%3E2018-11-01T00:00:00.000000Z&satNo=25544"
    
    url="https://unifieddatalibrary.com/udl/elset"
    params = {
        'epoch' : '>2018-11-01T00:00:00.000000Z',
        'satNo' : '25544'
    }
    url_with_args = f"{url}?{urlencode(params)}"
    
    response = http.request('GET', url_with_args, headers=headers)
    status_code = response.status

    if status_code != 200:
        raise urllib3.exceptions.HTTPError(status_code)    


    json_resp = json.loads(response.data.decode())  # "utf-8"

    return json_resp

if __name__ == '__main__':
    import pdb
    
    result = lambda_handler(event = {}, context = {})
    
    print(len(result))