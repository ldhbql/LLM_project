import configparser
import json
import os
import requests

config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.ini"))
base_url = config["default"]["base_url"]
model = config["default"]["model"]
api_key = config["default"]["api_key"]

messages = []

while True:
    print()
    print("请输入你的问题？")
    prompt = input()
    print("---")

    messages.append({"role": "user", "content": prompt})

    resp = requests.post(
        base_url.rstrip("/") + "/chat/completions",
        headers={"Authorization": "Bearer " + api_key},
        json={"model": model, "messages": messages, "stream": True},
        stream=True,
    )
    reply = ""
    for line in resp.iter_lines():
        if line and line.startswith(b"data: ") and line != b"data: [DONE]":
            delta = json.loads(line[6:])["choices"][0]["delta"]
            content = delta.get("content") or ""
            reply += content
            print(content, end="", flush=True)
    messages.append({"role": "assistant", "content": reply})
