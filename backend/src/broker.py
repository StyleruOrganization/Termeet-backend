import aio_pika


class RabbitMQClient:
    def __init__(self, url: str):
        self.url: str = url
        self.connection: aio_pika.Connection | None = None
        self.channel: aio_pika.Channel | None = None

    async def connect(self):
        self.connection = await aio_pika.connect_robust(
            self.url, fail_fast=True
        )
        self.channel = await self.connection.channel()

    async def close(self):
        if self.channel:
            await self.channel.close()
        if self.connection:
            await self.connection.close()

    async def publish(self, queue_name: str, message: aio_pika.Message):
        if not self.channel:
            raise RuntimeError(
                "Channel is not initialized. Call connect() first."
            )

        await self.channel.declare_queue(queue_name, durable=True)
        await self.channel.default_exchange.publish(
            message,
            routing_key=queue_name,
        )
