import string
import secrets
from flask import request
from application import db
from application.v1.models.models_auth import UserGroup, User, Session, AccessLog


class AuthService(object):
	def __init__(self):
		pass


	@staticmethod
	def create_user_group(group_name):
		group = UserGroup(group_name=group_name)
		db.session.add(group)
		db.session.commit()
		return {'msg': 'User group created'}, None, 200


	def create_user(self, user_data=None):
		if not user_data:
			user_data = request.get_json()
		try:
			username = user_data['username']
			group_id = user_data['group_id']
			api_key = self._generate_api_key()
			user = User(username=username, group_id=group_id, api_key=api_key)
			db.session.add(user)
			db.session.commit()
			return self.read_user_by_id(user_id=user.id)
		except Exception as e:
			db.session.rollback()
			error, code = {'error': f"User not created: an error occurred: {str(e)[:250]}"}, 500
			response = None
		return response, error, code


	@staticmethod
	def read_users():
		users = User.query.all()
		users_data = [{'id': user.id, 'username': user.username, 'group_id': user.group_id, 'api_key': user.api_key}
					  for user in users]
		return users_data, None, 200


	@staticmethod
	def read_user_by_id(user_id):
		user = User.query.get(user_id)
		if not user:
			return None, {'error': 'No user found'}, 404
		user_data = {'id': user.id, 'username': user.username, 'group_id': user.group_id, 'api_key': user.api_key}
		return user_data, None, 200


	def update_user_by_id(self, user_id, user_data=None):
		user = User.query.get(user_id)
		if not user:
			return None, {'error': 'No user found'}, 404

		if not user_data:
			user_data = request.get_json()
		try:
			for col in ['username', 'group_id']:
				if col in user_data:
					setattr(user, col, user_data[col])
			db.session.commit()
			return self.read_user_by_id(user_id=user.id)
		except Exception as e:
			db.session.rollback()
			error, code = {'error': f"User not updated: an error occurred: {str(e)[:250]}"}, 500
			response = None
		return response, error, code


	@staticmethod
	def delete_user_by_id(user_id):
		user = User.query.get(user_id)
		if not user:
			return None, {'error': 'No user found'}, 404
		username = user.username
		db.session.delete(user)
		db.session.commit()
		return {'msg': f'user {username} successfully deleted.'}, None, 200


	@staticmethod
	def _generate_api_key(length=64):
		alphabet = string.ascii_letters + string.digits
		api_key = ''.join(secrets.choice(alphabet) for _ in range(length))
		return api_key


