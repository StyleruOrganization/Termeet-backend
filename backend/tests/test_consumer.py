import asyncio

import aio_pika

from backend.src.config import config


# Сюда нужно передать канал
async def test_consumer():
    # Получить уже существующую очередь
    connection = await aio_pika.connect_robust(
        host=config.rabbitmq.HOST,
        port=config.rabbitmq.PORT,
        login=config.rabbitmq.USER,
        password=config.rabbitmq.PASSWORD,
        virtualhost="/",
    )

    channel = await connection.channel()

    queue = await channel.declare_queue(
        name="termeet_queue",
        durable=True,
    )

    async with queue.iterator() as queue_iter:
        async for message in queue_iter:
            async with message.process():
                # если здесь нет исключения — автоматически отправится ack
                # если исключение — отправится nack с requeue=False
                print(f"Received message: {message.body.decode()}")
