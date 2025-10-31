import boto3
from application import application
from application.v1.models.models_auth import *


def get_s3_client():
	access_key = application.config['S3_ACCESS_KEY']
	secret_key = application.config['S3_SECRET_KEY']
	s3_client = boto3.client('s3', aws_access_key_id=access_key, aws_secret_access_key=secret_key)
	return s3_client


def get_files_list_from_s3(bucket_name, prefix):
	s3_client = get_s3_client()
	continuation_token = None
	all_files = []
	while True:
		if not continuation_token:
			response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
		else:
			response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix, ContinuationToken=continuation_token)
		if 'Contents' in response:
			files = [obj['Key'] for obj in response['Contents'] if '.' in obj['Key']]
			all_files.extend(files)
		if not response.get('IsTruncated', False):
			break
		continuation_token = response['NextContinuationToken']
		print(len(all_files))
	return all_files


def load_data_from_aws_s3(bucket_name, file_name):
	s3_client = get_s3_client()
	response = s3_client.get_object(Bucket=bucket_name, Key=file_name)
	s3_data = response['Body'].read()
	return s3_data


def get_config_files_from_s3():
	bucket_name = application.config['S3_BUCKET']
	s3_client = get_s3_client()
	response = s3_client.list_objects_v2(Bucket=bucket_name)
	files = [obj['Key'] for obj in response['Contents'] if '.' in obj['Key']]
	return files


def download_data_from_s3(s3_filepath, data_filepath):
	bucket_name = application.config['S3_BUCKET']
	s3_client = get_s3_client()
	s3_client.download_file(bucket_name, s3_filepath, data_filepath)


def create_user_tables():
	if application.config['ENV'] == 'development':
		with application.app_context():
			db.create_all()
			print('Created auth tables')


def create_test_tables():
	if application.config['ENV'] == 'development':
		with application.app_context():
			from application.v1.models.models_test import db
			db.create_all()
			print('Created test tables')
