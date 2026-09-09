import json
import os
from uuid import UUID

import pika


def open_broker_connection():
    parameters = pika.URLParameters(os.environ["RABBITMQ_URL"])
    parameters.socket_timeout = 5
    parameters.stack_timeout = 10
    parameters.blocked_connection_timeout = 30

    return pika.BlockingConnection(parameters)


def publish_processing_run(run_id: UUID, correlation_id: str):
    queue_name = os.environ["RABBITMQ_QUEUE"]
    connection = open_broker_connection()

    try:
        channel = connection.channel()
        channel.queue_declare(queue=queue_name, durable=True)
        channel.confirm_delivery()

        message = {
            "run_id": str(run_id),
            "correlation_id": correlation_id,
        }

        channel.basic_publish(
            exchange="",
            routing_key=queue_name,
            body=json.dumps(message).encode("utf-8"),
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2,
                correlation_id=correlation_id,
                message_id=str(run_id),
            ),
            mandatory=True,
        )
    finally:
        if connection.is_open:
            connection.close()
