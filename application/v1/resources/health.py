from flask_restx import Resource, Namespace


ns_health = Namespace("health check",
					  path='/health/',
					  description='api endpoints for checking health of the application')


@ns_health.route("/")
class HealthResource(Resource):

	@ns_health.doc(security='apikey')
	# @api_key_required
	def get(self):
		return {'msg': 'It works!'}, 200


