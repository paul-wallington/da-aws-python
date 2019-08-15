#!/usr/bin/env python3
import snowflake.connector
import os
from common import Functions

env = os.environ['env']

print('Getting parameters from parameter store...')

param = '/snowflake/' + env + '/ac-param'
ac = Functions.get_parameter(param, False)

param = '/snowflake/' + env + '/un-param'
un = Functions.get_parameter(param, False)

param = '/snowflake/' + env + '/pw-param'
pw = Functions.get_parameter(param, True)

# Gets the version
conn = snowflake.connector.connect(
    user='paul.wallington@tfgm.com',
    password='Blackb3rry19',
    account='tfgm.eu-west-1'
    )
cs = conn.cursor()
try:
    sql = "SELECT current_version()"
    cs.execute(sql)
    one_row = cs.fetchone()
    print(one_row[0])
finally:
    cs.close()
conn.close()