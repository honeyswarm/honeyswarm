"""Replay sample honeypot JSON events onto MQTT for end-to-end validation.

Stands in for the not-yet-built hive agent: publishes event envelopes to
``hive/{hive_id}/events`` so the ingest service -> Mongo + OpenSearch -> WS
path can be exercised before any real hive exists.

Usage:
    python -m tools.replay_events --hive test --normalizer cowrie --count 5
"""
import argparse
import asyncio
import json
import os

import aiomqtt

SAMPLES = {
    "cowrie": {
        "peerIP": "203.0.113.7",
        "protocol": "ssh",
        "username": "root",
        "password": "123456",
        "eventid": "cowrie.login.failed",
    },
    "pyrdp": {"source_ip": "198.51.100.23", "eventid": "rdp.connection"},
    "http": {"src_ip": "192.0.2.44", "method": "GET", "path": "/wp-login.php"},
}


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("MQTT_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("MQTT_PORT", "1883")))
    parser.add_argument("--username", default=os.environ.get("MQTT_USERNAME", "honeyswarm"))
    parser.add_argument("--password", default=os.environ.get("MQTT_PASSWORD", ""))
    parser.add_argument("--hive", default="test")
    parser.add_argument("--normalizer", default="cowrie", choices=list(SAMPLES))
    parser.add_argument("--instance", default="replay-instance")
    parser.add_argument("--count", type=int, default=1)
    args = parser.parse_args()

    topic = f"hive/{args.hive}/events"
    async with aiomqtt.Client(
        hostname=args.host,
        port=args.port,
        username=args.username or None,
        password=args.password or None,
    ) as client:
        for i in range(args.count):
            envelope = {
                "normalizer": args.normalizer,
                "honeypot_instance_id": args.instance,
                "payload": dict(SAMPLES[args.normalizer], seq=i),
            }
            await client.publish(topic, json.dumps(envelope).encode("utf-8"))
            print(f"published {args.normalizer} event {i + 1}/{args.count} to {topic}")


if __name__ == "__main__":
    asyncio.run(main())
