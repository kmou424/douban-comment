import argparse
import csv
import json
import os
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv


@dataclass
class BookInfo:
    """书籍基本信息"""

    title: str
    author: str
    subject_id: str


class DoubanCommentCrawler:
    """豆瓣读书评论区爬虫"""

    BASE_URL = "https://book.douban.com"

    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }

    def __init__(self):
        load_dotenv()
        self.cookies = self._load_cookies()
        self.output_dir = self._load_output_dir()
        self.session = self._init_session()

    def _load_cookies(self) -> Optional[str]:
        return os.getenv("DOUBAN_COOKIES")

    def _extract_ck_from_cookies(self) -> Optional[str]:
        """从 cookies 中提取 ck 值

        Returns:
            ck 值，如果不存在则返回 None
        """
        # 首先尝试从 session cookies 中获取（最可靠）
        if hasattr(self, "session") and self.session:
            ck_cookie = self.session.cookies.get("ck")
            if ck_cookie:
                return ck_cookie

        # 如果 session 中没有，尝试从环境变量的 cookies 字符串中解析
        if not self.cookies:
            return None

        # cookies 可能是 cookie 字符串，格式如 "name1=value1; name2=value2"
        if "=" in self.cookies or ";" in self.cookies:
            # 解析 cookie 字符串
            cookie_parts = self.cookies.split(";")
            for part in cookie_parts:
                part = part.strip()
                if "=" in part:
                    key, value = part.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    if key == "ck":
                        return value

        return None

    def _load_output_dir(self) -> str:
        """加载输出文件夹，默认为 ./output"""
        return os.getenv("OUTPUT_DIR", "./output")

    def _init_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update(self.DEFAULT_HEADERS)
        if self.cookies:
            # 如果 cookies 是完整的 cookie 字符串，解析并设置所有 cookies
            if "=" in self.cookies or ";" in self.cookies:
                # 解析 cookie 字符串，格式如 "name1=value1; name2=value2"
                cookie_parts = self.cookies.split(";")
                for part in cookie_parts:
                    part = part.strip()
                    if "=" in part:
                        key, value = part.split("=", 1)
                        key = key.strip()
                        value = value.strip()
                        session.cookies.set(key, value)
            else:
                # 如果只是单个值，假设是 dbcl2
                session.cookies.set("dbcl2", self.cookies)
        return session

    def get(self, url: str, **kwargs) -> requests.Response:
        response = self.session.get(url, **kwargs)
        # 确保正确设置编码
        if response.encoding is None or response.encoding == "ISO-8859-1":
            # requests 默认使用 ISO-8859-1，但豆瓣使用 UTF-8
            response.encoding = "utf-8"

        # 总限流器：每次请求后随机等待 0.5-2 秒
        delay = random.uniform(0.5, 2.0)
        time.sleep(delay)

        return response

    def post(self, url: str, **kwargs) -> requests.Response:
        return self.session.post(url, **kwargs)

    def fetch_book_info(self, subject_id: str) -> BookInfo:
        """获取书籍基本信息

        Args:
            subject_id: 书籍 subject-id

        Returns:
            BookInfo 对象
        """
        url = f"{self.BASE_URL}/subject/{subject_id}/"
        response = self.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # 从 JSON-LD 中提取书名和作者
        title = ""
        author = ""

        # 查找 JSON-LD script 标签
        json_ld_script = soup.find("script", type="application/ld+json")
        if json_ld_script:
            try:
                data = json.loads(json_ld_script.string)
                title = data.get("name", "")
                authors = data.get("author", [])
                if authors and isinstance(authors, list) and len(authors) > 0:
                    author = authors[0].get("name", "")
            except (json.JSONDecodeError, AttributeError):
                pass

        # 如果 JSON-LD 中没有，尝试从 meta 标签获取
        if not title:
            og_title = soup.find("meta", property="og:title")
            if og_title:
                title = og_title.get("content", "")

        if not author:
            book_author = soup.find("meta", property="book:author")
            if book_author:
                author = book_author.get("content", "")

        return BookInfo(title=title, author=author, subject_id=subject_id)

    def fetch_comment_counts(self, subject_id: str) -> dict[str, int]:
        """获取三类评论总数

        Args:
            subject_id: 书籍 subject-id

        Returns:
            字典，键为 status（P/N/F），值为评论数量
        """
        url = f"{self.BASE_URL}/subject/{subject_id}/comments/"
        response = self.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        counts = {}

        # 查找评论标签
        comment_tabs = soup.find_all("li", class_="CommentTabs")
        if not comment_tabs:
            # 尝试另一种选择器
            comment_tabs = soup.select("ul.CommentTabs li")

        for tab in comment_tabs:
            text = tab.get_text()
            # 匹配 "读过(4916)" 这样的格式
            match = re.search(r"(读过|在读|想读)\((\d+)\)", text)
            if match:
                comment_type = match.group(1)
                count = int(match.group(2))

                # 映射到 status
                status_map = {"读过": "P", "在读": "N", "想读": "F"}
                status = status_map.get(comment_type)
                if status:
                    counts[status] = count

        return counts

    def build_comment_url(
        self, subject_id: str, page: int = 1, status: str = "P"
    ) -> str:
        """构建评论页面 URL（使用 comments_only=1 API）

        Args:
            subject_id: 书籍 subject-id
            page: 页码（从1开始）
            status: 评论状态，P=读过，N=在读，F=想读

        Returns:
            完整的评论页面 URL
        """
        base_url = f"{self.BASE_URL}/subject/{subject_id}/comments/"

        # 如果已登录，添加 ck 参数
        ck_value = self._extract_ck_from_cookies()
        ck_param = f"&ck={ck_value}" if ck_value else ""

        if page == 1:
            # 第一页不需要 start 参数
            return f"{base_url}?percent_type=&limit=20&status={status}&sort=score&comments_only=1{ck_param}"
        else:
            # 从第二页开始，start = (page - 1) * 20
            start = (page - 1) * 20
            return f"{base_url}?percent_type=&start={start}&limit=20&status={status}&sort=score&comments_only=1{ck_param}"

    def fetch_comments_page(
        self, subject_id: str, page: int = 1, status: str = "P"
    ) -> dict:
        """获取评论页面数据

        Args:
            subject_id: 书籍 subject-id
            page: 页码（从1开始）
            status: 评论状态，P=读过，N=在读，F=想读

        Returns:
            JSON 响应字典，包含 r 和 html 字段
        """
        url = self.build_comment_url(subject_id, page, status)
        print(url)
        # 构建 referer
        if page == 1:
            referer = f"{self.BASE_URL}/subject/{subject_id}/comments/?limit=20&status={status}&sort=score"
        else:
            start = (page - 1) * 20
            referer = f"{self.BASE_URL}/subject/{subject_id}/comments/?start={start}&limit=20&status={status}&sort=score"

        headers = self.DEFAULT_HEADERS.copy()
        headers["Referer"] = referer

        response = self.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    def parse_comments_from_html(self, html_content: str) -> list[dict]:
        """使用 BeautifulSoup 解析 HTML 中的评论

        Args:
            html_content: HTML 内容字符串

        Returns:
            评论列表，每个评论是一个字典
        """
        soup = BeautifulSoup(html_content, "html.parser")
        comments = []

        # 查找评论列表
        comment_items = soup.find_all("li", class_="comment-item")

        for item in comment_items:
            comment_data = {}

            # 提取评论 ID（从 li 标签的 data-cid 属性）
            comment_id = item.get("data-cid", "")
            if not comment_id:
                continue  # 没有评论 ID 则跳过
            comment_data["comment_id"] = comment_id

            # 提取用户信息：从 span.comment-info 中的第一个 a 标签（排除 comment-time）
            comment_info = item.find("span", class_="comment-info")
            if comment_info:
                # 找到 comment-info 中的所有 a 标签，排除 comment-time 类的
                all_links = comment_info.find_all("a")
                for link in all_links:
                    # 用户名链接没有 class 或 class 不包含 comment-time
                    link_class = link.get("class", [])
                    if "comment-time" not in link_class:
                        comment_data["user"] = link.get_text(strip=True)
                        comment_data["user_url"] = link.get("href", "")
                        break

            # 提取评分：从 span.rating 的 class 中提取 allstarXX
            rating_elem = item.find("span", class_="rating")
            rating_value = None
            if rating_elem:
                # 从 class 中提取星级（allstar10, allstar20, allstar30, allstar40, allstar50）
                rating_class = rating_elem.get("class", [])
                for cls in rating_class:
                    if cls.startswith("allstar"):
                        # 去除 "allstar" 前缀，获取数字部分
                        star_num_str = cls.replace("allstar", "")
                        try:
                            # 将数字除以 10 得到星级（10->1, 20->2, ..., 50->5）
                            rating_value = int(star_num_str) / 10
                        except ValueError:
                            pass
                        break
            comment_data["rating"] = rating_value if rating_value is not None else "无"

            # 提取评论内容：从 p.comment-content 中的 span.short
            # 必须先从 p.comment-content 找到，再找里面的 span.short，避免爬错到日期
            comment_content_p = item.find("p", class_="comment-content")
            if comment_content_p:
                short_span = comment_content_p.find("span", class_="short")
                if short_span:
                    comment_data["content"] = short_span.get_text(strip=True)
                else:
                    # 如果没有 span.short，可能是空评论
                    comment_data["content"] = ""
            else:
                comment_data["content"] = ""

            # 提取时间：从 a.comment-time 标签
            time_elem = item.find("a", class_="comment-time")
            if time_elem:
                comment_data["time"] = time_elem.get_text(strip=True)
                comment_data["comment_url"] = time_elem.get("href", "")

            # 提取地点：从 span.comment-location
            location_elem = item.find("span", class_="comment-location")
            if location_elem:
                location_text = location_elem.get_text(strip=True)
                if location_text:
                    comment_data["location"] = location_text

            # 提取有用数：从 span.vote-count
            vote_count_elem = item.find("span", class_="vote-count")
            if vote_count_elem:
                try:
                    comment_data["vote_count"] = int(
                        vote_count_elem.get_text(strip=True)
                    )
                except ValueError:
                    comment_data["vote_count"] = 0

            comments.append(comment_data)

        return comments

    def crawl_comments(
        self, subject_id: str, status: str = "P", max_comments: int = 100
    ) -> list[dict]:
        """爬取评论，最多爬取指定数量

        Args:
            subject_id: 书籍 subject-id
            status: 评论状态，P=读过，N=在读，F=想读
            max_comments: 最多爬取的评论数量（未登录时最多 100 条）

        Returns:
            评论列表（已去重）
        """
        # 使用 dict 以评论 ID 为键去重
        comments_dict = {}
        start = 0  # 使用 start 参数而不是 page

        while len(comments_dict) < max_comments:
            try:
                # 计算当前页码（用于显示）
                page = (start // 20) + 1 if start > 0 else 1

                # 构建 URL，使用实际的 start 值
                if start == 0:
                    # 第一页不需要 start 参数
                    url = self.build_comment_url(subject_id, page=1, status=status)
                else:
                    # 使用实际的 start 值
                    base_url = f"{self.BASE_URL}/subject/{subject_id}/comments/"
                    ck_value = self._extract_ck_from_cookies()
                    ck_param = f"&ck={ck_value}" if ck_value else ""
                    url = f"{base_url}?percent_type=&start={start}&limit=20&status={status}&sort=score&comments_only=1{ck_param}"

                # 构建 referer
                if start == 0:
                    referer = f"{self.BASE_URL}/subject/{subject_id}/comments/?limit=20&status={status}&sort=score"
                else:
                    referer = f"{self.BASE_URL}/subject/{subject_id}/comments/?start={start}&limit=20&status={status}&sort=score"

                headers = self.DEFAULT_HEADERS.copy()
                headers["Referer"] = referer

                response = self.get(url, headers=headers)
                response.raise_for_status()
                result = response.json()

                if result.get("r") != 0:
                    print(f"获取第 {page} 页失败: {result}")
                    break

                html_content = result.get("html", "")
                if not html_content:
                    print(f"第 {page} 页没有更多评论")
                    break

                comments = self.parse_comments_from_html(html_content)
                if not comments:
                    print(f"第 {page} 页解析到 0 条评论，停止爬取")
                    break

                # 使用评论 ID 去重（对所有排序方式都生效）
                new_count = 0
                for comment in comments:
                    comment_id = comment.get("comment_id", "")
                    if comment_id and comment_id not in comments_dict:
                        comments_dict[comment_id] = comment
                        new_count += 1

                print(
                    f"已爬取第 {page} 页（start={start}），获得 {len(comments)} 条评论（新增 {new_count} 条），总计 {len(comments_dict)} 条"
                )

                # 如果实际返回的评论数为 0，说明没有更多评论
                if len(comments) == 0:
                    print("没有更多评论，停止爬取")
                    break

                # start 的计算：
                # - 如果实际返回的评论数 = 20，则 start += 20（正常情况）
                # - 如果实际返回的评论数 < 20，则 start += 实际数量（避免跳过评论）
                # 去重不影响 start 的计算，只是用来避免重复保存
                if len(comments) < 20:
                    start += len(comments)
                else:
                    start += 20

                # 限制最多爬取 max_comments 条
                if len(comments_dict) >= max_comments:
                    break

            except Exception as e:
                print(f"爬取第 {page} 页（start={start}）时出错: {e}")
                break

        return list(comments_dict.values())

    def save_to_csv(self, comments: list[dict], filename: str) -> None:
        """将评论保存为 CSV 文件

        Args:
            comments: 评论列表
            filename: 输出文件名
        """
        if not comments:
            print("没有评论可保存")
            return

        # CSV 列顺序：comment_id, user, content, rating, time, location, vote_count
        fieldnames = [
            "comment_id",
            "user",
            "content",
            "rating",
            "time",
            "location",
            "vote_count",
        ]

        with open(filename, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for comment in comments:
                vote_count = comment.get("vote_count", "")
                # 将 vote_count 转换为字符串
                if vote_count == "":
                    vote_count = ""
                else:
                    vote_count = str(vote_count)

                row = {
                    "comment_id": comment.get("comment_id", ""),
                    "user": comment.get("user", ""),
                    "content": comment.get("content", ""),
                    "rating": comment.get("rating", ""),
                    "time": comment.get("time", ""),
                    "location": comment.get("location", ""),
                    "vote_count": vote_count,
                }
                writer.writerow(row)

        print(f"已保存 {len(comments)} 条评论到 {filename}")

    def sanitize_filename(self, text: str) -> str:
        """清理文件名，移除不合法字符

        Args:
            text: 原始文本

        Returns:
            清理后的文件名
        """
        # 移除或替换不合法字符
        invalid_chars = r'[<>:"/\\|?*]'
        text = re.sub(invalid_chars, "_", text)
        # 移除首尾空格和点
        text = text.strip(" .")
        return text


def main():
    parser = argparse.ArgumentParser(description="豆瓣读书评论区爬虫")
    parser.add_argument(
        "subject_id",
        type=str,
        help="书籍的 subject-id（例如: 10583099）",
    )

    args = parser.parse_args()

    crawler = DoubanCommentCrawler()
    print("豆瓣读书评论区爬虫已初始化")
    print(f"目标 subject-id: {args.subject_id}")
    print("排序方式: score（按评分）\n")

    # 获取书籍基本信息
    print("正在获取书籍信息...")
    book_info = crawler.fetch_book_info(args.subject_id)
    print(f"书名: {book_info.title}")
    print(f"作者: {book_info.author}\n")

    # 获取三类评论总数
    print("正在获取评论统计...")
    comment_counts = crawler.fetch_comment_counts(args.subject_id)
    status_names = {"P": "读过", "N": "在读", "F": "想读"}
    for status, count in comment_counts.items():
        print(f"{status_names.get(status, status)}: {count} 条")
    print()

    # 分别爬取三类评论
    for status, count in comment_counts.items():
        status_name = status_names.get(status, status)
        print(f"\n开始爬取 {status_name} 评论...")

        # 如果 cookies 不为空（已登录），使用评论总数；否则限制为 100 条
        if crawler.cookies:
            max_comments = count
            print(f"已登录，将爬取全部 {count} 条评论")
        else:
            max_comments = min(count, 100)
            print(f"未登录，最多爬取 {max_comments} 条评论")

        comments = crawler.crawl_comments(
            args.subject_id, status=status, max_comments=max_comments
        )

        if comments:
            # 确保输出目录存在
            os.makedirs(crawler.output_dir, exist_ok=True)

            # 生成文件名：<书名>_<作者名>_<评论类型>评论_年月日_时分秒.csv
            title = crawler.sanitize_filename(book_info.title)
            author = crawler.sanitize_filename(book_info.author)
            # 获取当前时间戳，格式：年月日_时分秒
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{title}_{author}_{status_name}评论_{timestamp}.csv"
            output_file = os.path.join(crawler.output_dir, filename)
            crawler.save_to_csv(comments, output_file)
        else:
            print(f"未获取到 {status_name} 评论")


if __name__ == "__main__":
    main()
