import os
from pepper.libpepper import Pepper

class PepperApi():
    def __init__(self):
        self.api = Pepper(os.environ.get("SALT_HOST"))
        self.api_auth()



    def api_auth(self):
        print("Pepper Auth")
        self.api.login(os.environ.get("SALT_USERNAME"), os.environ.get("SALT_SHARED_SECRET"), 'sharedsecret')


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

    def delete_key(self, minion_id):
        """Given a Minion ID will delete the key from the salt master"""
        api_reponse = self.api.low([{'client': 'wheel', 'fun': 'key.delete', 'match':minion_id}])
        if api_reponse['return'][0]['data']['success']:
            return api_reponse['return'][0]['data']['return']

    def run_client_function_async(self, target, function):
        """
        Basic Function Runner; for things like test.ping it is up to the receiving function to parse the data it needs. 
        Makes Async Call returns Job ID
        """
        api_reponse = self.api.low([{'client': 'local_async', 'tgt': target, 'fun': function}])
        return api_reponse['return'][0]['jid']

    def run_client_function(self, target, function):
        """
        Basic Function Runner; for things like test.ping it is up to the receiving function to parse the data it needs. 
        Not async so blocking?
        """
        api_reponse = self.api.low([{'client': 'local', 'tgt': target, 'fun': function}])
        return api_reponse['return'][0]

    def apply_state(self, target, state_name):
        """
        Basic Function Runner; for things like test.ping it is up to the receiving function to parse the data it needs.
        Makes Async Call returns Job ID
        """
        api_reponse = self.api.low([{'client': 'local_async', 'tgt': target, 'fun': "state.apply", 'arg': [state_name]}])
        print(api_reponse)
        return api_reponse['return'][0]['jid']

    def lookup_job(self, job_id):
        api_response = self.api.lookup_jid(job_id)
        if len(api_response['return'][0]) == 0:
            return None
        else:
            return api_response['return'][0]
        

pepper_api = PepperApi()