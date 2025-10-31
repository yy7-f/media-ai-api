import os
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime
from flask import request, jsonify
from application import db, application
from application.v1.models.models_test import Customers


class CustomerService(object):
    def __init__(self):
        pass

    @staticmethod
    def create_customer(self, customer_data=None):
        if not customer_data:
            customer_data = request.get_json()
            print(f'customer_data: {customer_data}')
        try:
            record = Customers()
            # print(f'record: {record}')
            columns = ['payment_method_id', 'customer_number', 'customer_name', '_payment_date', 'address', 'invoice_name', 'invoice_address']
            # print(columns)
            # print(customer_data)
            for column in columns:
                if column in customer_data:
                    setattr(record, column, customer_data[column])
            # print(customer_data)
            payment_method_id = customer_data['payment_method_id']
            customer_number = customer_data['customer_number']
            customer_name = customer_data['customer_name']
            payment_date = datetime.strptime(customer_data['payment_date'], '%Y-%m-%d').date()
            # payment_date_str = customer_data['payment_date']  # Extract payment_date as string
            # payment_date = datetime.strptime(payment_date_str, '%Y-%m-%d')  # Convert payment_date to datetime object
            # payment_date = payment_date.isoformat()  # Convert payment_date to isoformat
            address = customer_data['address']
            invoice_name = customer_data['invoice_name']
            invoice_address = customer_data['invoice_address']
            customer = Customers(payment_method_id=payment_method_id, customer_number=customer_number, customer_name=customer_name,
                                 _payment_date=payment_date, address=address, invoice_name=invoice_name, invoice_address=invoice_address)
            db.session.add(customer)
            db.session.commit()
            return CustomerService.read_customer_by_id(customer_id=customer.id)
        except Exception as e:
            db.session.rollback()
            error, code = {'error': f"Customer not created: an error occurred: {str(e)[:250]}"}, 500
            response = None
        return response, error, code


    @staticmethod
    def read_customers():
        records = Customers.query.all()
        columns = ['id', 'payment_method_id', 'customer_number', 'customer_name', 'payment_date', 'address', 'invoice_name', 'invoice_address']
        response = [{column: getattr(record, column) for column in columns} for record in records]
        # print(response)
        return response, None, 200

    @staticmethod
    def read_customer_by_id(customer_id):
        try:
            record = Customers.query.get(customer_id)
            columns = ['id', 'payment_method_id', 'customer_number', 'customer_name', 'payment_date', 'address', 'invoice_name', 'invoice_address']
            response = {column: getattr(record, column) for column in columns}
            return response, None, 200
        except Exception as e:
            db.session.rollback()
            error, code = {'error': f"Customer not found: an error occurred: {str(e)[:250]}"}, 404
            response = None
        return response, error, code

    def update_customer_by_id(self, customer_id, customer_data=None):
        if not customer_data:
            customer_data = request.get_json()
        try:
            record = Customers.query.get(customer_id)
            print(record)
            columns = ['payment_method_id', 'customer_number', 'customer_name', '_payment_date', 'address', 'invoice_name', 'invoice_address']
            for column in columns:
                if column in customer_data:
                    setattr(record, column, customer_data[column])
            db.session.commit()
            return self.read_customer_by_id(customer_id=record.id)
        except Exception as e:
            db.session.rollback()
            error, code = {'error': f"Customer not updated: an error occurred: {str(e)[:250]}"}, 500
            response = None
            return response, error, code

    def delete_customer_by_id(self, customer_id):
        record = Customers.query.get(customer_id)
        if not record:
            return None, {'error': 'No customer found'}, 404
        db.session.delete(record)
        db.session.commit()
        return {'message': 'Customer deleted successfully'}, None, 200
