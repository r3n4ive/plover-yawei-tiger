import json
import os

BASE_DICT = {}
LONGEST_KEY = 10

def load_dict():
    global BASE_DICT
    dict_path = os.path.join(os.path.dirname(__file__), "aw-teding.json")
    with open(dict_path, "r", encoding="utf-8") as f:
        raw_dict = json.load(f)

    # 预处理：把字典中所有键里的 '/' 全替换成 '-'
    BASE_DICT.update({k.replace("-", "/"): v for k, v in raw_dict.items()})

load_dict()

def normalize_stroke(stroke):
    # 去掉开头结尾的 '-'，保持中间的 '-'
    stroke = stroke.strip('-')
    return stroke.replace('-', '/')

def lookup(outline):
    # outline 是笔划列表，比如 ['-SA-', 'SA-', '-TP']
    normalized = [normalize_stroke(s) for s in outline]
    key = '/'.join(normalized)
    return BASE_DICT.get(key)