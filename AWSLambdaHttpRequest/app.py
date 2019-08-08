import os
import sys
import boto3
import pyodbc
import json
import requests
from requests.exceptions import HTTPError
#import time
from datetime import datetime
from common import Functions


def read_from_rds(event, context):

    env = os.environ['env']
    print('Setting environment to ' + env + '...')

    dr = 'ODBC Driver 17 for SQL Server'

    print('Getting parameters from parameter store...')

    param = '/lambda-https-request/' + env + '/read-from-rds-ds-param'
    ds = Functions.get_parameter(param, False)

    param = '/lambda-https-request/' + env + '/read-from-rds-un-param'
    un = Functions.get_parameter(param, False)

    param = '/lambda-https-request/' + env + '/read-from-rds-pw-param'
    pw = Functions.get_parameter(param, True)

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
    s3bucket = Functions.get_parameter(param, False)
    print(f'Parameter {param} value is: {s3bucket}')

    param = '/lambda-https-request/' + env + '/ons-oa-lookup-url-param'
    base_url = Functions.get_parameter(param, False)
    print(f'Parameter {param} value is: {base_url}')

    param = '/lambda-https-request/' + env + '/max-loops-param'
    max_loops = int(Functions.get_parameter(param, False))
    print(f'Parameter {param} value is: {max_loops}')

    param = '/lambda-https-request/' + env + '/timeout-param'
    timeout = int(Functions.get_parameter(param, False))
    print(f'Parameter {param} value is: {timeout}')

    param = '/lambda-https-request/' + env + '/result-record-count'
    result_record_count = int(Functions.get_parameter(param, False))
    print(f'Parameter {param} value is: {result_record_count}')

    try:
        exceeded_transfer_limit = True
        counter = 0
        offset = 0
        url_result_record_count = 'resultRecordCount=' + str(result_record_count)
        event_list = json.loads(json.dumps(event, indent=4))
        attribute = event_list['attribute']
        print(f'Lookup attribute is: {attribute}')

        while exceeded_transfer_limit:

            curr_datetime = datetime.now()
            curr_datetime_str = curr_datetime.strftime('%Y%m%d_%H%M%S%f')
            filekey = attribute + '_' + curr_datetime_str + '_' + str(counter) + '.json'

            print('Building URL...')
            url_offset = 'resultOffset=' + str(offset)
            urls = [base_url, url_offset, url_result_record_count]
            join_urls = '&'.join(urls)
            url = join_urls.replace('<attribute>', attribute)
            print(f'URL: {url} built...')

            data = json.loads(json.dumps(api_call(url, timeout, filekey), indent=4, sort_keys=True))

            print('got here')
            print(len(data['features']))

            if data.get('exceededTransferLimit'):
                exceeded_transfer_limit = json.dumps(data['exceededTransferLimit'])
                print(exceeded_transfer_limit)
                if data.get('features'):
                    print('We have features')
                    offset += len(data['features'])
                else:
                    print('Json data does not contain features objects')
                    break
            else:

                offset = 0
                print('got here 2')
                exceeded_transfer_limit = False
                print(exceeded_transfer_limit)
                if data.get('features'):
                    print('We have features')
                else:
                    print('Json data does not contain features objects')
                    break

                print('got here 3')

            #print('Exceeded transfer limit: ' + str(exceeded_transfer_limit))

            print('got here 4')

            if counter == max_loops:
                print('You have reached the maximum number of loops(' + str(max_loops) + ')')
                break

            counter += 1

            upload_file_to_s3(s3bucket, filekey, data)

    except Exception as e:
        print(e)

    return event_list['elements']


def upload_file_to_s3(s3bucket, filekey, data):

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


