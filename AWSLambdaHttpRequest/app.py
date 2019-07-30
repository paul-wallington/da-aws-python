import os
import sys
import boto3
import pyodbc
from botocore.exceptions import ClientError, ParamValidationError
import json
import requests
from requests.exceptions import HTTPError
import time


def read_from_rds(event, context):

    env = os.environ['env']
    print('Setting environment to ' + env + '...')

    dr = 'ODBC Driver 17 for SQL Server'

    print('Getting parameters from parameter store...')

    param = '/lambda-https-request/' + env + '/read-from-rds-ds-param'
    ds = get_parameter(param, False)

    param = '/lambda-https-request/' + env + '/read-from-rds-un-param'
    un = get_parameter(param, False)

    param = '/lambda-https-request/' + env + '/read-from-rds-pw-param'
    pw = get_parameter(param, True)

    conn = sql_server_conn(dr, ds, un, pw)

    with conn:
        with conn.cursor() as cur:
            print('Building sql query...')
            sql = 'SELECT element FROM dbo.vwLocalAreaDistrictLookup FOR JSON AUTO ;'

            print('Attempting to read rows from sql query...')
            cur.execute(sql)
            result = cur.fetchall()
            for row in result:
                print('Building dictionary...')
                row_dict = json.loads((row[0]))
                print('Input json...' + row[0])
                return row_dict


def sql_server_conn(dr, ds, un, pw):

    try:
        print('Building sql connection...')
        print(f'Attempting to connect to {ds}...')
        conn = pyodbc.connect('DRIVER={%s};SERVER=%s;DATABASE=AWSAdmin;UID=%s;PWD=%s' % (dr, ds, un, pw))

    except pyodbc.Error as ex:
        sqlstate = ex.args[1]
        print(sqlstate)
        sys.exit()

    return conn


def check_json_array_for_elements(event, context):

    cnt = 0

    try:
        event_list = json.loads(json.dumps(event, indent=4))

        for element in event_list['elements']:
            cnt += 1
            print('Array element is: ' + element['element'])

        if cnt > 0:
            has_elements = True
            print(f'Array has {str(cnt)} Elements')
        else:
            has_elements = False
            print('Array is empty')

        return has_elements

    except Exception as e:
        print(e)


def get_first_element_from_json_array(event, context):

    cnt = 0

    try:
        event_list = json.loads(json.dumps(event, indent=4))

        for element in event_list['elements']:
            cnt += 1
            if cnt == 1:
                break
        print('First array element is: ' + element['element'])

        return element['element']

    except Exception as e:
        print(e)


def remove_next_element_from_json_array(event, context):

    cnt = 0

    try:
        event_list_json = json.dumps(event, indent=4)
        print(event_list_json)

        event_list = json.loads(json.dumps(event, indent=4))
        for element in event_list['elements']:
            cnt += 1
            if cnt == 1:
                attribute = element['element']
                print('First array element is: ' + attribute)
                break

        print(f'Remove element {attribute} from json array...')
        event_list_output = []
        for element in event_list['elements']:
            if attribute not in element["element"]:
                event_list_output.append(element)
        event_list["elements"] = event_list_output

        return event_list

    except Exception as e:
        print(e)


def get_http_request(event, context):

    env = os.environ['env']
    print(f'Setting environment to {env}...')

    print('Getting parameters from parameter store...')

    param = '/lambda-https-request/' + env + '/s3-bucket-param'
    s3bucket = get_parameter(param, False)
    print(f'Parameter {param} value is: {s3bucket}')

    param = '/lambda-https-request/' + env + '/ons-oa-lookup-url-param'
    base_url = get_parameter(param, False)
    print(f'Parameter {param} value is: {base_url}')

    try:
        event_list = json.loads(json.dumps(event, indent=4))
        attribute = event_list['attribute']
        print(f'Lookup attribute is: {attribute}')
        print('Building URL...')
        url = base_url.replace('<attribute>', attribute)
        print(f'URL: {url} built...')
        timeout = 60
        timestr = time.strftime("%Y%m%d_%H%M%S")
        filekey = attribute + '_' + timestr + '.json'

        upload_files_to_s3(s3bucket, filekey, api_call(url, timeout, filekey))

        return event_list['elements']

    except Exception as e:
        print(e)


def get_parameter(param, decrypt):

    try:
        ssm = boto3.client('ssm')
        param_response = ssm.get_parameter(Name=param, WithDecryption=decrypt)['Parameter']['Value']

    except ssm.exceptions.ParameterNotFound:
        print(f'Parameter {param} not found')
    except ParamValidationError as pve:
        print('Parameter validation error: %s' % pve)
    except ClientError as ce:
        print('Unexpected error: %s' % ce)
    else:
        print(f'Parameter {param} found')

        return param_response


def upload_files_to_s3(s3bucket, filekey, data):

    try:
        s3 = boto3.resource('s3')
        print(f'Uploading file {filekey} to {s3bucket}...')
        response = s3.Object(s3bucket, filekey).put(Body=json.dumps(data))
        if response['ResponseMetadata']['HTTPStatusCode'] != 200:
            raise Exception('s3 upload failed with code: {}'.format(response['ResponseMetadata']['HTTPStatusCode']))
        else:
            print(f'file {filekey} uploaded successfully to {s3bucket}')
            return {'statusCode': 200, 'body': response}
        return

    except Exception as e:
        print(e)


def api_call(url, timeout, filekey):

    try:
        print('Calling API...')
        http_response = requests.get(url=url, timeout=timeout)
        print('Adding filekey to json file...')
        http_response_json = http_response.json()
        http_response_json['fileKey'] = filekey
        http_response.raise_for_status()

    except HTTPError as http_err:
        print(f'HTTP error occurred: {http_err}')
    except Exception as err:
        print(f'Other error occurred: {err}')
    else:
        print('API call was successful')

    return http_response_json