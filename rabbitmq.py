import aio_pika
import asyncio
from aio_pika.pool import Pool


async def get_channel_pool() -> aio_pika.pool.Pool:
    loop = asyncio.get_event_loop()
    async def get_connection():
        return await aio_pika.connect_robust(host='127.0.0.1', port=5672, login='test',
                                             password='123456')

    connection_pool = Pool(get_connection, max_size=20, loop=loop)

    async def get_channel() -> aio_pika.Channel:
        async with connection_pool.acquire() as connection:
            return await connection.channel()

    return Pool(get_channel, max_size=20, loop=loop)