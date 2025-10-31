import json
from datetime import datetime, date
from flask import request


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, date):
            return obj.isoformat()  # Serialize date to ISO format string
        return super().default(obj)