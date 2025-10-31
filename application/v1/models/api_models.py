import datetime

from application.extensions import api
from flask_restx.fields import String, Integer, DateTime, Date
from application.v1.static.format import CustomJSONEncoder
import json

user_model = api.model("UserModel", {"username": String(example='user1'), "group_id": Integer(example=1), })

supply_point_model = api.model("SupplyPointModel", {"customer_id": String(example='1'),
                                                    "region_id": String(example='2'),
                                                    "spid": String(example='0300000123450000012345'),
                                                    "supply_point_name": String(example='ハンファビル'),
                                                    "supply_point_address": String(example='東京都南区１−１−１'),
                                                    'created_at': DateTime(example='2024-04-19T03:27:44.442799Z'),
                                                    'updated_at': DateTime(example='2024-04-19T03:27:44.442806Z'),
                                                    })

supply_point_update_model = api.model("SupplyPointUpdateModel", {"spid": String(example='0300000123450000012345'),
                                                                 "supply_point_name": String(example='ハンファビル'),
                                                                 "supply_point_address": String(example='東京都南区１−１−１'),
                                                                 'updated_at': DateTime(example='2024-04-19T03:27:44.442806Z')
                                                                 })


customer_model = api.model("CustomerModel", {"payment_method_id": String(example='1'),
                                             "customer_number": String(example='000001'),
                                             "customer_name": String(example='株式会社ハンファ'),
                                             "payment_date": String(example='2024-04-19'),
                                             # "payment_date": Date(example='2024-04-19'),
                                             # "payment_date": json.dumps(payment_date, cls=CustomJSONEncoder),
                                             "address": String(example='東京都南区１−１−１'),
                                             "invoice_name": String(example='株式会社ハンファ'),
                                             "invoice_address": String(example='東京都南区１−１−１'),
                                             'created_at': DateTime(example='2024-04-19T03:27:44.442806Z'),
                                             'updated_at': DateTime(example='2024-04-19T03:27:44.442806Z')})

customer_update_model = api.model("CustomerUpdateModel", {"customer_number": String(example='000001'),
                                                          "customer_name": String(example='株式会社ハンファ'),
                                                          "payment_date": String(example='2024-04-19'),
                                                          "address": String(example='東京都南区１−１−１'),
                                                          "invoice_name": String(example='株式会社ハンファ'),
                                                          "invoice_address": String(example='東京都南区１−１−１'),
                                                          'updated_at': DateTime(example='2024-04-19T03:27:44.442806Z'),})


