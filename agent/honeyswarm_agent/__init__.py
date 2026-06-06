"""Honeyswarm hive agent.

Runs on each Hive. Replaces the Salt minion: enrolls with the controller, then
maintains an MQTT session for commands (deploy/start/stop/remove honeypot
containers via the Docker SDK) and telemetry (heartbeat status + tailed honeypot
JSON-log events).
"""
__version__ = "2.2.0"
