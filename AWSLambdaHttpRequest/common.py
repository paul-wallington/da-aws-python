import boto3
from botocore.exceptions import ClientError, ParamValidationError
import re


class Functions:

    def get_parameter(self, decrypt):

        try:
            ssm = boto3.client('ssm')
            param_response = ssm.get_parameter(Name=self, WithDecryption=decrypt)['Parameter']['Value']

        except ssm.exceptions.ParameterNotFound:
            print(f'Parameter {self} not found')
        except ParamValidationError as pve:
            print('Parameter validation error: %s' % pve)
        except ClientError as ce:
            print('Unexpected error: %s' % ce)
        else:
            print(f'Parameter {self} found')

            return param_response

