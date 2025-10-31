from flask_restx import Resource, Namespace
from application.workers import api_key_required
from application.v1.services.customer_service import CustomerService
from application.v1.models.api_models import customer_model, customer_update_model
from datetime import datetime

ns_customers = Namespace("customers",
                         path='/customers/',
                         description='api endpoints for managing customer data.',
                         doc=False)

@ns_customers.route("/")
class CustomerResource(Resource):

    @ns_customers.doc(security='apikey', description='endpoint for creating a customer.')
    @ns_customers.expect(customer_model)
    # @api_key_required
    def post(self):
        response, error, code = CustomerService().create_customer(self, customer_data=None)
        if error:
            return error, code
        return response, code

    @ns_customers.doc(security='apikey', description='endpoint for reading all customers.')
    # @api_key_required
    def get(self):
        response, error, code = CustomerService().read_customers()
        if error:
            return error, code
        return response, code

@ns_customers.route("/<int:customer_id>/")
class CustomerResourceById(Resource):

    @ns_customers.doc(security='apikey', description='endpoint for reading a customer by id.')
    # @api_key_required
    def get(self, customer_id):
        response, error, code = CustomerService().read_customer_by_id(customer_id=customer_id)
        if error:
            return error, code
        return response, code

    @ns_customers.doc(security='apikey', description='endpoint for updating a customer by id.')
    @ns_customers.expect(customer_update_model)
    # @api_key_required
    def put(self, customer_id):
        response, error, code = CustomerService().update_customer_by_id(customer_id=customer_id)
        if error:
            return error, code
        return response, code

    @ns_customers.doc(security='apikey', description='endpoint for deleting a customer by id.')
    # @api_key_required
    def delete(self, customer_id):
        response, error, code = CustomerService().delete_customer_by_id(customer_id=customer_id)
        if error:
            return error, code
        return response, code

