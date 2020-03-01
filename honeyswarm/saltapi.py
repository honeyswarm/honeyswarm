import os
from pepper.libpepper import Pepper
from pepper.exceptions import PepperException

# https://docs.saltstack.com/en/latest/ref/clients/#python-client-api

class PepperApi():
    def __init__(self):
        self.authenticated = False
        self.api = Pepper(os.environ.get("SALT_HOST"))
        self.api_auth()



    def api_auth(self):
        try:
            print("Pepper Auth")
            self.api.login(os.environ.get("SALT_USERNAME"), os.environ.get("SALT_SHARED_SECRET"), 'sharedsecret')
            self.authenticated = True
        except PepperException as p:
            print(p)
            self.authenticated = False
        except Exception as e:
            self.authenticated = False


    def salt_keys(self):
        """
        Queries the Salt Master for all Minion keys

        Returns:
            dict: A dictionary with 3 lists for minions, pre-minions and rejected minions
        """
        api_reponse = self.api.low([{'client': 'wheel', 'fun': 'key.list_all'}])
        if api_reponse['return'][0]['data']['success']:
            return api_reponse['return'][0]['data']['return']

    def accept_key(self, minion_id):
        """
        Tells the Salt Master to Accept a Key by its name

        Args:
            minion_id (str): Minion ID - should be a Mongo ID from `Hive` modal 

        Returns:
            dict: A dictionary with the ID for any accepted minions. 
        """
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

    def apply_state(self, target, args_list):
        """
        Tells the Salt Master to apply a given state to a named minion

        Args:
            target (str): Minion ID - should be a Mongo ID from `Hive` modal 
            args_list (list): List of args. First element in list MUST be the Salt State to apply

        Returns:
            str: Salt Job ID 
        """
        api_reponse = self.api.low([{'client': 'local_async', 'tgt': target, 'fun': "state.apply", 'arg': args_list}])
        print(api_reponse)
        return api_reponse['return'][0]['jid']

    def lookup_job(self, job_id):
        """
        Query the Salt Master for a job by its Salt Job ID

        Args:
            job_id (str): Salt Job Id should be taken from PepperJobs Model 

        Returns:
            dict/None: Return None if job still pending else dictionary of all state modules and their outputs.  
        """
        # This is lazy but as this job runs frequently use it to check auth state
        try:
            api_response = self.api.lookup_jid(job_id)
            if len(api_response['return'][0]) == 0:
                return None
            else:
                return api_response['return'][0]
            print("hello")
        except PepperException as p:
            self.authenticated = False
            print(p)
            if p == 'Authentication denied':
                self.api_auth()
        except Exception as err:
            print(err)
        return None

pepper_api = PepperApi()