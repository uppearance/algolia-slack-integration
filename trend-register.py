"""
Algolia - Slack slash command (+ django webhook) Integration

1. slack에서 /algolia [keyword]를 검색하면 algolia index에서 해당 값이 포함된
검색 결과를 리턴해줌.
(2. slack app내의 "Interactivity & Shortcuts"를 사용해서 django webhook endpoint에
trending keyword를 등록해주는 workflow 완성 - 코드는 backend 서버에 포함)
"""
import os

from algoliasearch.search_client import SearchClient
from flask import Flask, abort, jsonify, request

app = Flask(__name__)

client = SearchClient.create(
    os.getenv("ALGOLIA_APPLICATION_ID"), os.getenv("ALGOLIA_SEARCH_API_KEY")
)


def is_request_valid(request):
    is_token_valid = request.form["token"] == os.getenv("SLACK_VERIFICATION_TOKEN")
    is_team_id_valid = request.form["team_id"] == os.getenv("SLACK_TEAM_ID")

    return is_token_valid and is_team_id_valid


def get_links(query):
    formatted_q = query.strip().replace(" ", "+")
    google_link = f"https://www.google.com/search?q={formatted_q}&oq={formatted_q}"
    youtube_link = (
        f"https://www.youtube.com/results?search_query={formatted_q}&oq={formatted_q}"
    )
    return (google_link, youtube_link)


def format_block_for(title, text, image_url):
    google_link, youtube_link = get_links(title)
    block = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": text + f"<{google_link}|Google>  |  <{youtube_link}|YouTube>\n",
            },
            "accessory": {
                "type": "image",
                "image_url": image_url,
                "alt_text": title,
            },
        }
    ]
    return block


def format_attachments_for(query, video_count, product_count):
    google_link, youtube_link = get_links(query)

    attachments = [
        {
            "title": "Register this keyword on server?",
            "text": (
                f"*Video*: `{video_count}` found\n*Product*: `{product_count}` found\n"
                f"<{google_link}|Google it>  |  <{youtube_link}|YouTube>\n"
            ),
            "fallback": "You are unable to register keyword on server",
            "callback_id": "wopr_game",
            "color": "#3AA3E3",
            "attachment_type": "default",
            "actions": [
                {
                    "name": "register",
                    "text": "Yes",
                    "style": "primary",
                    "type": "button",
                    "value": query,
                    "confirm": {
                        "title": "Are you sure?",
                        "text": "This will make this keyword go public on production",
                        "ok_text": "Yes",
                        "dismiss_text": "No",
                    },
                },
                {"name": "game", "text": "No", "type": "button", "value": "no"},
            ],
        }
    ]
    return attachments


@app.route("/trend-register", methods=["POST"])
def trend_register():
    query = request.form.get("text")
    if not query:
        abort(400)

    if not is_request_valid(request):
        abort(400)

    res = client.multiple_queries(
        [
            {"indexName": os.getenv("ALGOLIA_PRODUCT_INDEX_NAME"), "query": query},
            {"indexName": os.getenv("ALGOLIA_VIDEO_INDEX_NAME"), "query": query},
        ]
    )

    if video_count := res["results"][1]["nbHits"]:
        video = res["results"][1]["hits"][0]
        v_block = format_block_for(
            video["title"],
            f"*Title*: {video['title']}\n*Channel*: {video['yt_channel_name']}\n",
            video["video_thumbnail_url"],
        )
    else:
        v_block = []

    if product_count := res["results"][0]["nbHits"]:
        product = res["results"][0]["hits"][0]
        p_block = format_block_for(
            product["title"],
            f"*Title*: {product['title']}\n*Brand*: {product['brand']}\n",
            product["primary_image"],
        )
    else:
        p_block = []

    # format messages
    blocks = (
        p_block
        + v_block
        + [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Searched on Algolia Indices with keyword: *`{query}`*",
                },
            }
        ]
    )
    attachments = format_attachments_for(query, video_count, product_count)

    return jsonify(
        response_type="in_channel",
        attachments=attachments,
        blocks=blocks,
    )
