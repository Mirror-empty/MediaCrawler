import argparse
import asyncio
import json
import sys
import aio_pika
from aio_pika import ExchangeType
from aio_pika.abc import AbstractIncomingMessage

import config
import db
from base.base_crawler import AbstractCrawler
from media_platform.bilibili import BilibiliCrawler
from media_platform.douyin import DouYinCrawler
from media_platform.kuaishou import KuaishouCrawler
from media_platform.weibo import WeiboCrawler
from media_platform.xhs import XiaoHongShuCrawler
from rabbitmq import get_channel_pool


class CrawlerFactory:
    CRAWLERS = {
        "xhs": XiaoHongShuCrawler,
        "dy": DouYinCrawler,
        "ks": KuaishouCrawler,
        "bili": BilibiliCrawler,
        "wb": WeiboCrawler
    }

    @staticmethod
    def create_crawler(platform: str) -> AbstractCrawler:
        crawler_class = CrawlerFactory.CRAWLERS.get(platform)
        if not crawler_class:
            raise ValueError("Invalid Media Platform Currently only supported xhs or dy or ks or bili ...")
        return crawler_class()


async def run(config_params: config.ConfigParams):
    for _ in range(3):
        try:

            # init db
            if config.SAVE_DATA_OPTION == "db":
                await db.init_db()

            crawler = CrawlerFactory.create_crawler(platform=config_params.platform)
            crawler.init_config(
                platform=config_params.platform,
                login_type=config_params.lt,
                crawler_type=config_params.type,
                start_page=config_params.start,
                keyword=config_params.keywords,
                account=config_params.accounts
            )
            await crawler.start()

            if config.SAVE_DATA_OPTION == "db":
                await db.close()
            break
        except Exception as e:
            print(f"Error occurred for account {config_params}: {e}")
            # 异常情况下，等待一段时间后重试
            await asyncio.sleep(5)


async def consume() -> None:
    channel_pool = await get_channel_pool()
    async with channel_pool.acquire() as channel:
        # await channel.set_qos(20)
        direct_exchange = await channel.declare_exchange(
            config.TASK_EXCHANGW_NAME, ExchangeType.DIRECT, durable=True
        )
        queue_name = config.TASK_QUEUE_NAME

        queue = await channel.declare_queue(
            queue_name, durable=False, auto_delete=False,
        )
        await queue.bind(direct_exchange, routing_key=queue_name)
        async with queue.iterator() as queue_iter:
            message: AbstractIncomingMessage
            async for message in queue_iter:
                try:
                    decoded_message =message.body.decode()
                    print("decoded_message-->", decoded_message)
                    config_dict = json.loads(decoded_message)
                    config_param = config.ConfigParams(**config_dict)
                    await run(config_param)
                except Exception as e:
                    print('message nacked, exception=', e)
                    await message.nack(requeue=False)
                else:
                    print('task finished')
                    try:
                        await message.ack()
                    except:
                        await channel.reopen()


async def main():
    tasks = []
    for _ in range(100):
        task = asyncio.ensure_future(consume())
        tasks.append(task)
    await asyncio.gather(*tasks)


if __name__ == '__main__':
    try:
        # asyncio.run(main())
        asyncio.get_event_loop().run_until_complete(main())
    except KeyboardInterrupt:
        sys.exit()
