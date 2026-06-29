import asyncio

import aio_pika

from backend.src.config import config


async def test_get_connection():
    print("Connecting to RabbitMQ...")
    connection = await aio_pika.connect_robust(
        host=config.rabbitmq.HOST,
        port=config.rabbitmq.PORT,
        login=config.rabbitmq.USER,
        password=config.rabbitmq.PASSWORD,
        virtualhost="/",
    )

    channel = await connection.channel(
        publisher_confirms=True,
        on_return_raises=False,
    )

    await channel.set_qos(prefetch_count=1)

    exchange = await channel.declare_exchange(
        name="termeet_exchange",
        type=aio_pika.ExchangeType.DIRECT,
        durable=True,
    )

    queue = await channel.declare_queue(
        name="termeet_queue",
        durable=True,
    )

    await queue.bind(exchange, routing_key="termeet_routing_key")

    message = aio_pika.Message(
        body="Hello, RabbitMQ!".encode(),
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )

    await exchange.publish(message, routing_key="termeet_routing_key")


# if __name__ == "__main__":
#     asyncio.run(get_connection())

# Получить уже существующий exchange не создавая новый
# exchange = await channel.get_exchange("my_exchange", ensure=True)
# ensure=True — бросит исключение если exchange не существует