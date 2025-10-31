import os
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime
from flask import request, jsonify
from application import db, application
from application.v1.models.models_test import SupplyPoints


class SupplyPointService(object):
    def __init__(self):
        pass

    @staticmethod
    def create_supply_point(self, supply_point_data=None):
        if not supply_point_data:
            supply_point_data = request.get_json()
        try:
            record = SupplyPoints()
            columns = ['customer_id', 'region_id', 'spid', 'supply_point_name', 'supply_point_address']
            for column in columns:
                if column in supply_point_data:
                    setattr(record, column, supply_point_data[column])
            customer_id = supply_point_data['customer_id']
            region_id = supply_point_data['region_id']
            spid = supply_point_data['spid']
            supply_point_name = supply_point_data['supply_point_name']
            supply_point_address = supply_point_data['supply_point_address']
            supply_point = SupplyPoints(customer_id=customer_id, region_id=region_id, spid=spid,
                                        supply_point_name=supply_point_name, supply_point_address=supply_point_address)
            db.session.add(supply_point)
            db.session.commit()
            return SupplyPointService.read_supply_point_by_id(supply_point_id=supply_point.id)
        except Exception as e:
            db.session.rollback()
            error, code = {'error': f"Supply point not created: an error occurred: {str(e)[:250]}"}, 500
            response = None
        return response, error, code

    @staticmethod
    def read_supply_points():
        records = SupplyPoints.query.all()
        columns = ['id', 'customer_id', 'region_id', 'spid', 'supply_point_name', 'supply_point_address']
        response = [{column: getattr(record, column) for column in columns} for record in records]
        return response, None, 200


    @staticmethod
    def read_supply_point_by_id(supply_point_id):
        try:
            record = SupplyPoints.query.get(supply_point_id)
            columns = ['id', 'customer_id', 'region_id', 'spid', 'supply_point_name', 'supply_point_address']
            response = {column: getattr(record, column) for column in columns}
            return response, None, 200
        except Exception as e:
            db.session.rollback()
            error, code = {'error': f"Supply point not found: an error occurred: {str(e)[:250]}"}, 404
            response = None
        return response, error, code

    def update_supply_point_by_id(self, supply_point_id, supply_point_data=None):
        if not supply_point_data:
            supply_point_data = request.get_json()
        try:
            record = SupplyPoints.query.get(supply_point_id)
            columns = ['customer_id', 'region_id', 'spid', 'supply_point_name', 'supply_point_address']
            for column in columns:
                if column in supply_point_data:
                    setattr(record, column, supply_point_data[column])
            db.session.commit()
            return self.read_supply_point_by_id(record.id)
        except Exception as e:
            db.session.rollback()
            error, code = {'error': f"Supply point not updated: an error occurred: {str(e)[:250]}"}, 500
            response = None
            return response, error, code

    def delete_supply_point_by_id(self, supply_point_id):
        record = SupplyPoints.query.get(supply_point_id)
        if not record:
            return None, {'error': 'No supply point found'}, 404
        db.session.delete(record)
        db.session.commit()
        return {'message': 'Supply point deleted successfully'}, None, 200
