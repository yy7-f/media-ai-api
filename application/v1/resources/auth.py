from flask_restx import Resource, Namespace
from application.workers import api_key_required
from application.v1.services.auth_services import AuthService
from application.v1.models.api_models import user_model


ns_auth = Namespace("authorizations",
					path='/users/',
					description='api endpoints for managing user authorizations and authentication within the API.',
					doc=False)


@ns_auth.route("/")
class AuthResource(Resource):

	@ns_auth.doc(security='apikey', description='endpoint for creating a user.')
	@ns_auth.expect(user_model)
	@api_key_required
	def post(self):
		response, error, code = AuthService().create_user()
		if error:
			return error, code
		return response, code


	@ns_auth.doc(security='apikey', description='endpoint for reading all users.')
	@api_key_required
	def get(self):
		response, error, code = AuthService().read_users()
		return response, code



@ns_auth.route("/<int:user_id>/")
class AuthResourceById(Resource):

	@ns_auth.doc(security='apikey', description='endpoint for reading a user by id.')
	@api_key_required
	def get(self, user_id):
		response, error, code = AuthService().read_user_by_id(user_id=user_id)
		if error:
			return error, code
		return response, code


	@ns_auth.expect(user_model)
	@ns_auth.doc(security='apikey', description='endpoint for updating a user by id.')
	@api_key_required
	def put(self, user_id):
		response, error, code = AuthService().update_user_by_id(user_id=user_id)
		if error:
			return error, code
		return response, code


	@ns_auth.doc(security='apikey', description='endpoint for deleting a user by id.')
	@api_key_required
	def delete(self, user_id):
		response, error, code = AuthService().delete_user_by_id(user_id=user_id)
		if error:
			return error, code
		return response, code

