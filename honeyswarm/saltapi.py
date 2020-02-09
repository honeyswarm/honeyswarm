import os
from pepper.libpepper import Pepper

class PepperApi():
    def __init__(self, app):
        print(1)
        self.api = Pepper(os.environ.get("SALT_HOST"))
        self.api.login(os.environ.get("SALT_USERNAME"), os.environ.get("SALT_SHARED_SECRET"), 'sharedsecret')
        print(2)


    def salt_ping(self, targets):
        try:
            api_response = self.api.low([{'client': 'local', 'tgt': targets, 'fun': 'test.ping'}])
            responses = api_response['return']
            return responses
        except Exception as err:
            print(err)
            return []

    def salt_keys(self):
        """Gets a list of keys from the salt server"""
        api_reponse = self.api.low([{'client': 'wheel', 'fun': 'key.list_all'}])
        if api_reponse['return'][0]['data']['success']:
            return api_reponse['return'][0]['data']['return']

    def accept_key(self, minion_id):
        """Given a Minion ID will accept the key in the salt stack"""
        api_reponse = self.api.low([{'client': 'wheel', 'fun': 'key.accept', 'match':minion_id}])
        if api_reponse['return'][0]['data']['success']:
            return api_reponse['return'][0]['data']['return']

    def run_client_function(self, target, function):
        """Basic Function Runner; for things like test.ping it is up to the receiving function to parse the data it needs. """
        api_reponse = self.api.low([{'client': 'local', 'tgt': target, 'fun': function}])
        print(api_reponse)
        return api_reponse['return'][0]