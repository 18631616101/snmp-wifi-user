from easysnmp import Session, snmp_walk
import hashlib
import requests
import base64
from datetime import datetime
import urllib.parse
import json
import mysql.connector

# 接口信息
base_url = "http://******/DrcomSrv/DrcomService"
iusername = "******"
sign_key = "**********"
interface_code = "S14"

# 创建MySQL数据库连接
db = mysql.connector.connect(
    host="localhost",  # 请根据您的MySQL配置更改主机名
    user="******",  # 请更改为实际的用户名
    password="*********",  # 请更改为实际的密码
    database="apinfo"  # 数据库名称
)

# 创建游标对象
cursor = db.cursor()

# 打开文件并逐行读取
with open('/root/snmpst/csrd/apoid.txt', 'r') as file:
    for line in file:
        # 拆分每行以获取OID、AP名称、位置和楼层
        parts = line.strip().split(' ')
        if len(parts) >= 4:
            ap_oid, ap_name, location, floor = parts[:4]

            # 执行 SNMP Walk
            results = snmp_walk(ap_oid, hostname='10.252.100.62', community='Jcdx@public', version=2)

            # 从 SNMP Walk 结果中提取 IP 地址
            ip_addresses = []
            if results:
                for result in results:
                    ip_addresses.append(result.value)

            # 存储已处理的帐号的集合
            unique_accounts = set()

            # 循环查询每个 IP 地址
            for ip_to_query in ip_addresses:
                # 构建请求参数
                params = {
                    "code": interface_code,
                    "ip": ip_to_query,
                }

                # 将参数转换为 JSON 字符串
                params_json = json.dumps(params)

                # 对参数进行 Base64 编码
                business_data = base64.b64encode(params_json.encode()).decode()

                # 获取当前时间戳，格式化为 yyyyMMddhhmmss
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

                # 构建签名前的字符串
                pre_sign_string = business_data + timestamp + sign_key

                # 对预处理字符串进行 MD5 签名
                sign = hashlib.md5(pre_sign_string.encode()).hexdigest()

                # 对 business 参数进行 URL 编码
                business_data_encoded = urllib.parse.quote(business_data)

                # 构建 GET 请求 URL
                url = f"{base_url}?iusername={iusername}&business={business_data_encoded}&timestamp={timestamp}&sign={sign}"

                # 发送 GET 请求
                response = requests.get(url)

                # 处理响应
                if response.status_code == 200:
                    response_data = response.json()
                    if "list" in response_data and len(response_data["list"]) > 0:
                        account = response_data["list"][0].get("account")
                        unique_accounts.add(account)

            # 打印每次请求得到的总条数
            total_unique_accounts = len(unique_accounts)

            # 获取当前系统时间
            query_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 尝试插入新数据，如果 oid 值已存在，则执行更新
            sql = """INSERT INTO ap_values (value, oid, ap_name, query_time, location, floor) 
                     VALUES (%s, %s, %s, %s, %s, %s)
                     ON DUPLICATE KEY UPDATE 
                     value = VALUES(value), ap_name = VALUES(ap_name), query_time = VALUES(query_time), location = VALUES(location), floor = VALUES(floor)"""

            val = (total_unique_accounts, ap_oid, ap_name, query_time, location, floor)

            cursor.execute(sql, val)
            db.commit()

# 关闭数据库连接
db.close()
