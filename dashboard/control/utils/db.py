import os
from pymongo import MongoClient

def get_db():
    uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
    client = MongoClient(uri)
    return client.get_database('anjani_dashboard')
