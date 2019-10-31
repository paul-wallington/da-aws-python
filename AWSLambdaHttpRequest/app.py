import os
import json
from datetime import datetime
from common import Functions
#import snowflake.connector


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

    conn = Functions.sql_server_conn(dr, ds, un, pw)

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


def get_ons_oa_http_request(event, context):

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

    param = '/lambda-https-request/' + env + '/max-error-loops-param'
    max_error_loops = int(Functions.get_parameter(param, False))
    print(f'Parameter {param} value is: {max_error_loops}')

    try:
        exceeded_transfer_limit = True
        counter = 1
        error_counter = 1
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

            while error_counter < max_error_loops:
                print('Attempting to load api (' + str(error_counter) + ') of (' + str(max_error_loops) + ')...')
                data = Functions.load_api(filekey, timeout, url)
                if data.get('error'):
                    print(f'API returned error message: {data}')
                else:
                    break
                error_counter += 1
                if error_counter == max_error_loops:
                    print('You have reached the maximum number of error loops (' + str(max_error_loops) + ')')
                    break

            if data.get('exceededTransferLimit'):
                exceeded_transfer_limit = json.dumps(data['exceededTransferLimit'])
            else:
                exceeded_transfer_limit = False
                offset = 0

            if data.get('features'):
                number_of_features = len(data['features'])
                offset += number_of_features
                print(f'Json string for {attribute} loop {counter} contains {number_of_features} features')
            else:
                print('Json data does not contain features objects')
                break

            if counter == max_loops:
                print('You have reached the maximum number of loops (' + str(max_loops) + ')')
                break

            counter += 1

            Functions.upload_file_to_s3(s3bucket, filekey, data)

    except Exception as e:
        print(e)

    return event_list['elements']

#
#def snowflake_validate(event, context):

#    env = os.environ['env']
#    print('Setting environment to ' + env + '...')

#    print('Getting parameters from parameter store...')

#    param = '/snowflake/' + env + '/ac-param'
#    ac = Functions.get_parameter(param, False)

#    param = '/snowflake/' + env + '/un-param'
#    un = Functions.get_parameter(param, False)

#    param = '/snowflake/' + env + '/pw-param'
#    pw = Functions.get_parameter(param, True)

#    # connect to snowflake data warehouse
#    conn = snowflake.connector.connect(
#        account=ac,
#        user=un,
#        password=pw
#    )

#    sql = "SELECT current_version()"

#    with conn:
#        with conn.cursor() as cur:
#            cur.execute(sql)
#            one_row = cur.fetchone()
#            print(one_row[0])