ElasticSearch
=============

Installation
------------
There is a customer docker-compose that you can use to additionaly launch a single node ElasticSearch and Kibana stack. 
You will need to modify the default password to ensure that your Kibana instance is secured against unathorised access. 


Migration
---------

If you already have data in your HoneySwarm you can add this data to your ElasticSearch using the following steps.

1. Connect to the HoneySwarm docker container 
2. Start ``flask shell``
3. Run the following python code. 

.. code-block:: python

   import json
   import datetime
   from elasticsearch import Elasticsearch
   elastic_client = Elasticsearch("honeyswarm_es01", http_auth=("elastic", "HoneySwarm"))
   from honeyswarm.models import HoneypotEvents
   events = HoneypotEvents.objects()
   for event in events:
   # If you already have data in your elastic index use this datetime filter to avoid duplicates. 
   if event.date < datetime.datetime.strptime("2020-07-31 21:23:42.000000", '%Y-%m-%d %H:%M:%S.%f'):
      try:
         event_entry = json.loads(event.to_json())
         event_entry["event_id"] = str(event_entry['_id'])
         del event_entry['_id']
         event_entry['date'] = event.date
         instance_id = event_entry['honeypot_instance_id']
         index_name = "honeyswarm-{0}".format(instance_id)
         elastic_client.index(index=index_name,body=event_entry)
      except Exception as err:
         print(err)