from flask_restx import Resource, Namespace
from application.workers import api_key_required
from application.v1.services.supply_point_service import SupplyPointService
from application.v1.models.api_models import supply_point_model, supply_point_update_model

supply_points_ns = Namespace("supply_points",
                             path='/supply_points/',
                             description='api endpoints for managing supply points data.',
                             doc=False)


@supply_points_ns.route("/")
class SupplyPointResource(Resource):

    @supply_points_ns.doc(security='apikey', description='endpoint for creating a supply point.')
    @supply_points_ns.expect(supply_point_model)
    # @api_key_required
    def post(self):
        response, error, code = SupplyPointService().create_supply_point(self, supply_point_data=None)
        if error:
            return error, code
        return response, code


    @supply_points_ns.doc(security='apikey', description='endpoint for reading all supply points.')
    # @api_key_required
    def get(self):
        response, error, code = SupplyPointService().read_supply_points()
        if error:
            return error, code
        return response, code


@supply_points_ns.route("/<int:supply_point_id>/")
class SupplyPointResourceById(Resource):

    @supply_points_ns.doc(security='apikey', description='endpoint for reading a supply point by id.')
    # @api_key_required
    def get(self, supply_point_id):
        response, error, code = SupplyPointService().read_supply_point_by_id(supply_point_id=supply_point_id)
        if error:
            return error, code
        return response, code

    @supply_points_ns.doc(security='apikey', description='endpoint for updating a supply point by id.')
    @supply_points_ns.expect(supply_point_update_model)
    # @api_key_required
    def put(self, supply_point_id):
        response, error, code = SupplyPointService().update_supply_point_by_id(supply_point_id=supply_point_id)
        if error:
            return error, code
        return response, code

    @supply_points_ns.doc(security='apikey', description='endpoint for deleting a supply point by id.')
    # @api_key_required
    def delete(self, supply_point_id):
        response, error, code = SupplyPointService().delete_supply_point_by_id(supply_point_id=supply_point_id)
        if error:
            return error, code
        return response, code
