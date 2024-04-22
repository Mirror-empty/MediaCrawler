import asyncio
import argparse
import json

from aio_pika import DeliveryMode, ExchangeType, Message, connect

import config


async def main() -> None:
    # Perform connection
    connection = await connect(host='127.0.0.1', port=5672, login='test',
                               password='123456')

    parser = argparse.ArgumentParser(description='Media crawler program.')
    parser.add_argument('--platform', type=str, help='Media platform select (xhs | dy | ks | bili | wb)',
                        choices=["xhs", "dy", "ks", "bili", "wb"], default=config.PLATFORM)
    parser.add_argument('--lt', type=str, help='Login type (qrcode | phone | cookie)',
                        choices=["qrcode", "phone", "cookie"], default=config.LOGIN_TYPE)
    parser.add_argument('--type', type=str, help='crawler type (search | detail | creator)',
                        choices=["search", "detail", "creator"], default=config.CRAWLER_TYPE)
    parser.add_argument('--start', type=int, help='crawler type (number of start page)',
                        default=config.START_PAGE)
    parser.add_argument('--keywords', type=str, help='crawler type (please input keywords)',
                        default=config.KEYWORDS)
    parser.add_argument('--accounts', type=str, help='crawler type (please input keywords)',
                        default=config.User_Account)

    args = parser.parse_args()

    async with connection:
        # Creating a channel
        channel = await connection.channel()
        logs_exchange = await channel.declare_exchange(
            config.TASK_EXCHANGW_NAME, ExchangeType.DIRECT, durable=True
        )
        # Sending the message
        for account in args.accounts.split(","):
            config_params = config.ConfigParams(
                platform=args.platform,
                lt=args.lt,
                type=args.type,
                start=args.start,
                keywords=args.keywords,
                accounts=account,
            )
            message_body = json.dumps(config_params.to_dict())
            message = Message(
                body=message_body.encode(),
                delivery_mode=DeliveryMode.PERSISTENT,
            )
            await asyncio.sleep(1)

            routing_key = config.TASK_QUEUE_NAME

            await logs_exchange.publish(message, routing_key=routing_key)

            print(f" [x] Sent {message.body!r}")


if __name__ == "__main__":
    asyncio.run(main())
