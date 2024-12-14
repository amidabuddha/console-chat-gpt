import re

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from rich.console import Console

from console_gpt.prompts.system_prompt import system_reply


def _fetch_html(url) -> tuple[str, bool]:
    """
    Fetch HTML content from a URL, acting as a web browser
    :param url: URL to fetch
    :return: HTML and bool whether or not the request succeeded
    """
    console = Console()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
    }

    if not (url.startswith("http://") or url.startswith("https://")):
        url = "https://" + url

    with console.status("[bold cyan]Scraping the page...", spinner="earth"):
        try:
            response = requests.get(url, headers=headers)
            # Raise an exception for HTTP error codes
            response.raise_for_status()
        except requests.HTTPError as http_err:
            return f"HTTP error occurred: {http_err}", False
        except Exception as err:
            return f"An error occurred: {err}", False
        return response.text, True


def _clean_html(html_content) -> str:
    """
    Remove unnecessary HTML tags
    :param html_content: HTML content
    :return: HTML without unnecessary HTML tags"""
    soup = BeautifulSoup(html_content, "html.parser")

    # List of unnecessary tags you might want to remove
    useless_tags = [
        "script",
        "style",
        "meta",
        "link",
        "head",
        "noscript",
        "footer",
        "iframe",
        "input",
        "form",
        "comment",
    ]
    for tag in useless_tags:
        for script in soup(tag):
            script.decompose()

    return str(soup)


def _convert_html_to_markdown(html) -> str:
    """
    Convert HTML to Markdown to reduce token usage
    :param html: HTML content
    :return: Markdown
    """
    markdown_text_raw = md(html)
    # Remove useless empty lines from purged HTML
    markdown_text = re.sub(r"\n{3,}", "\n\n", markdown_text_raw).strip()
    return markdown_text


def page_content(url: str) -> tuple[str, int]:
    """
    Fetch content from the web, convert the source code from
    HTML to Markdown for better prompts and less token usage
    :param url: URL to browse
    :return: Markdown and status_code (whether the request failed or not)
    """
    if not url:
        return "", False
    html_content, success = _fetch_html(url)
    if success:
        cleaned_html = _clean_html(html_content)
        markdown_output = _convert_html_to_markdown(cleaned_html)
        if markdown_output:
            return markdown_output, success
        system_reply(url, "[ERROR] No content was found on the page:")
        return "", False
    system_reply(html_content, "[ERROR] Failed to fetch the content due to:")
    return "", success
