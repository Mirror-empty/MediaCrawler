# -*- coding: utf-8 -*-
import asyncio
import json
from typing import Any, Callable, Dict, Optional, List
from urllib.parse import urlencode

import httpx
from playwright.async_api import BrowserContext, Page

import config
from base.base_crawler import AbstractApiClient
from tools import utils

from .exception import DataFetchError
from .graphql import KuaiShouGraphQL


class KuaiShouClient(AbstractApiClient):
    def __init__(
            self,
            timeout=10,
            proxies=None,
            *,
            headers: Dict[str, str],
            playwright_page: Page,
            cookie_dict: Dict[str, str],
            browser_context: BrowserContext
    ):
        self.proxies = proxies
        self.timeout = timeout
        self.headers = headers
        self._host = "https://www.kuaishou.com/graphql"
        self.playwright_page = playwright_page
        self.cookie_dict = cookie_dict
        self.graphql = KuaiShouGraphQL()
        self.browser_context = browser_context

    async def request(self, method, url, **kwargs) -> Any:
        async with httpx.AsyncClient(proxies=self.proxies) as client:
            response = await client.request(
                method, url, timeout=self.timeout,
                **kwargs
            )
        data: Dict = response.json()
        if data.get("errors"):
            raise DataFetchError(data.get("errors", "unkonw error"))
        else:
            return data.get("data", {})

    async def get(self, uri: str, params=None) -> Dict:
        final_uri = uri
        if isinstance(params, dict):
            final_uri = (f"{uri}?"
                         f"{urlencode(params)}")
        return await self.request(method="GET", url=f"{self._host}{final_uri}", headers=self.headers)

    async def post(self, uri: str, data: dict) -> Dict:
        json_str = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        return await self.request(method="POST", url=f"{self._host}{uri}",
                                  data=json_str, headers=self.headers)

    async def Browerpost(self, uri: str, data: dict) -> Dict:

        uri = f"{self._host}{uri}"
        fetch_request = {
            "method": "POST",
            "headers": self.headers,
            "body": json.dumps(data)
        }

        data = await self.playwright_page.evaluate(
            """ ([fetchRequest,uri]) => {
                return (async () => {
                  const response = await fetch(uri, fetchRequest);
                  return response.ok ? await response.json() : null;
                })();   
            }""",
            [fetch_request, uri]
        )

        if data is None:
            raise DataFetchError(data)
        else:
            return data.get("data", {})


    async def pong(self) -> bool:
        """get a note to check if login state is ok"""
        utils.logger.info("[KuaiShouClient.pong] Begin pong kuaishou...")
        ping_flag = False
        try:
            post_data = {
                "operationName": "visionProfileUserList",
                "variables": {
                    "ftype": 1,
                },
                "query": self.graphql.get("vision_profile")
            }
            res = await self.post("", post_data)
            if res.get("visionProfileUserList", {}).get("result") == 1:
                ping_flag = True
        except Exception as e:
            utils.logger.error(f"[KuaiShouClient.pong] Pong kuaishou failed: {e}, and try to login again...")
            ping_flag = False
        return ping_flag


    async def update_cookies(self, browser_context: BrowserContext):
        cookie_str, cookie_dict = utils.convert_cookies(await browser_context.cookies())
        self.headers["Cookie"] = cookie_str
        self.cookie_dict = cookie_dict


    async def search_info_by_keyword(self, keyword: str, pcursor: str):
        """
        KuaiShou web search api
        :param keyword: search keyword
        :param pcursor: limite page curson
        :return:
        """
        post_data = {
            "operationName": "visionSearchPhoto",
            "variables": {
                "keyword": keyword,
                "pcursor": pcursor,
                "page": "search"
            },
            "query": self.graphql.get("search_query")
        }

        return await self.Browerpost("", post_data)


    async def get_video_info(self, photo_id: str) -> Dict:
        """
        Kuaishou web video detail api
        :param photo_id:
        :return:
        """
        post_data = {
            "operationName": "visionVideoDetail",
            "variables": {
                "photoId": photo_id,
                "page": "search"
            },
            "query": self.graphql.get("video_detail")
        }
        return await self.post("", post_data)


    async def get_video_comments(self, photo_id: str, pcursor: str = "") -> Dict:
        """get video comments
        :param photo_id: photo id you want to fetch
        :param pcursor: last you get pcursor, defaults to ""
        :return:
        """
        post_data = {
            "operationName": "commentListQuery",
            "variables": {
                "photoId": photo_id,
                "pcursor": pcursor
            },
            "query": self.graphql.get("comment_list")

        }

        return await self.Browerpost("", post_data)


    async def get_video_sub_comments(self, photo_id: str, pcursor: str = "", rootCommentId: str = "") -> Dict:
        """get video comments
        :param photo_id: photo id you want to fetch
        :param pcursor: last you get pcursor, defaults to ""
        :param rootCommentId: 父级评论id
        :return:
        """
        post_data = {
            "operationName": "visionSubCommentList",
            "variables": {
                "photoId": photo_id,
                "pcursor": pcursor,
                "rootCommentId": rootCommentId
            },
            "query": self.graphql.get("sub_comment_list")

        }
        return await self.post("", post_data)


    async def get_video_all_comments(self, photo_id: str, crawl_interval: float = 1.0, is_fetch_sub_comments=False,
                                     callback: Optional[Callable] = None):
        """
        get video all comments include sub comments
        :param photo_id:
        :param crawl_interval:
        :param is_fetch_sub_comments:
        :param callback:
        :return:
        """

        result = []
        # 第一次为空
        pcursor = ""

        while pcursor != "no_more":
            comments_res = await self.get_video_comments(photo_id, pcursor)
            vision_commen_list = comments_res.get("visionCommentList", {})
            pcursor = vision_commen_list.get("pcursor", "")
            comments = vision_commen_list.get("rootComments", [])

            if callback:  # 如果有回调函数，就执行回调函数 插入
                await callback(photo_id, comments)

            result.extend(comments)
            await asyncio.sleep(crawl_interval)
            if not is_fetch_sub_comments:
                continue
            # todo handle get sub comments
            sub_comments = await self.get_comments_all_sub_comments(photo_id, comments, crawl_interval, callback)
            result.extend(sub_comments)
        return result


    async def get_comments_all_sub_comments(self, photo_id: str, comments: List[Dict], crawl_interval: float = 1.0,
                                            callback: Optional[Callable] = None) -> List[Dict]:
        """
        获取指定一级评论下的所有二级评论, 该方法会一直查找一级评论下的所有二级评论信息
        Args:
            comments: 评论列表
            crawl_interval: 爬取一次评论的延迟单位（秒）
            callback: 一次评论爬取结束后

        Returns:

        jump out of: "pcursor": "no_more",
        """
        if not config.ENABLE_GET_SUB_COMMENTS:
            utils.logger.info(
                f"[KuaiShouClient.get_comments_all_sub_comments] Crawling sub_comment mode is not enabled")
            return []

        result = []
        for comment in comments:

            rootcommentId = comment.get("commentId")

            subCommentsPcursor = comment.get("subCommentsPcursor")
            if subCommentsPcursor is None:
                utils.logger.info(
                    f"[KuaiShouClient.get_comments_all_sub_comments] No 'comments' key found in continuecontinue: {comment}")
                continue

            subComments = comment.get("subComments")

            if subComments and callback:
                utils.logger.info(
                    f"[KuaiShouClient.get_comments_all_sub_comments] No 'comments' key found in subCommentssubCommentssubCommentssubComments: {subComments}")
                await callback(photo_id, subComments)

            while subCommentsPcursor:
                comments_res = await self.get_video_sub_comments(photo_id, subCommentsPcursor, rootcommentId)
                comments_res = comments_res.get("visionSubCommentList")
                if not comments_res.get("subComments"):
                    utils.logger.info(
                        f"[KuaiShouClient.get_comments_all_sub_comments] No 'subComments' key found in response: {comments_res}")
                    break
                subCommentsPcursor = comments_res.get("pcursor")
                subComments = comments_res["subComments"]
                if callback:  # 如果有回调函数，就执行回调函数 插入
                    await callback(photo_id, subComments)

                await asyncio.sleep(crawl_interval)
                result.extend(subComments)

        return result
