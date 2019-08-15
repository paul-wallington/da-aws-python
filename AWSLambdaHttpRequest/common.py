import boto3
from botocore.exceptions import ClientError, ParamValidationError
import requests
from requests.exceptions import HTTPError
import json
import sys
import pyodbc


class Functions:

    @staticmethod
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

    @staticmethod
    def get_parameter(param_name, decrypt):

        try:
            ssm = boto3.client('ssm')
            param_response = ssm.get_parameter(Name=param_name, WithDecryption=decrypt)['Parameter']['Value']

        except ssm.exceptions.ParameterNotFound:
            print(f'Parameter {param_name} not found')
        except ParamValidationError as pve:
            print('Parameter validation error: %s' % pve)
        except ClientError as ce:
            print('Unexpected error: %s' % ce)
        else:
            print(f'Parameter {param_name} found')

            return param_response

    @staticmethod
    def api_call(url, timeout, filekey):

        try:
            print('Calling API...')
            http_response = requests.get(url=url, timeout=timeout)
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

    @staticmethod
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

    @staticmethod
    def load_api(filekey, timeout, url):
        data = json.loads(json.dumps(Functions.api_call(url, timeout, filekey), indent=4, sort_keys=True))
        return data
