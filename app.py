import csv
import random
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

BASE_DIR = Path(__file__).parent
DB_PATH  = BASE_DIR / "comments.db"
CSV_PATH = BASE_DIR / "naver_map_restaurants_menus.csv"

CUISINE_MAP = {
    '한식': ['김치', '된장', '비빔', '냉면', '삼겹', '갈비', '육개장', '순두부', '설렁탕', '곰탕',
              '만두', '전골', '불고기', '보쌈', '족발', '국밥', '찌개', '구이', '제육', '막회',
              '육회', '수육', '쌈', '오징어', '해물', '고등어', '갈치', '순대', '미나리',
              '굴', '물회', '갈비탕', '꽃게', '뚝배기', '떡', '전', '회'],
    '중식': ['짜장', '짬뽕', '탕수육', '마파두부', '볶음밥', '딤섬', '교자', '소롱포', '탄탄면',
              '마라', '쇼마이', '기스면', '팔진', '하교', '우육', '사천', '부추굴'],
    '일식': ['라멘', '스시', '초밥', '돈까스', '우동', '소바', '덴뿌라', '야키', '사시미',
              '규동', '오마카세', '편백', '샤브샤브', '규카츠', '가츠'],
    '양식': ['파스타', '피자', '스테이크', '버거', '리조또', '샌드위치', '브런치',
              '에스프레소', '와인', '맥주', '아이스크림', '마리또조'],
}

THEME_MAP = {
    '해장용 🍜': ['해장', '국밥', '설렁탕', '육개장', '순댓국', '콩나물', '순두부', '곰탕', '해장라면'],
    '든든한 한끼 🍱': ['정식', '백반', '도시락', '비빔밥', '덮밥', '볶음밥'],
    '고기 먹고 싶다 🥩': ['삼겹', '갈비', '목살', '차돌', '직화', '소고기', '한우', '구이', '불고기'],
    '면 생각날 때 🍝': ['냉면', '우동', '라멘', '짬뽕', '짜장', '파스타', '탄탄면', '막국수', '쫄면', '소바'],
}


def detect_cuisine(text: str) -> list:
    result = [c for c, kws in CUISINE_MAP.items() if any(k in text for k in kws)]
    return result or ['기타']


def detect_themes(text: str, avg: float) -> list:
    themes = [t for t, kws in THEME_MAP.items() if any(k in text for k in kws)]
    if avg and avg < 10000:
        themes.append('가성비 👍')
    return themes


def load_restaurants() -> list:
    data = defaultdict(lambda: {
        'name': '', 'address': '', 'open_time': '', 'menu_items': [], 'prices': []
    })

    with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            name = row.get('place_name', '').strip()
            if not name:
                continue
            d = data[name]
            d['name'] = name
            d['address'] = row.get('address', '').strip()
            d['open_time'] = row.get('open_time_text', '').strip()
            menu = row.get('menu_name', '').strip()
            # lunch.py 버전에 따라 'price' 또는 'price_krw' 컬럼 사용
            raw_price = row.get('price') or row.get('price_krw') or row.get('price_raw') or ''
            digits = re.sub(r'[^\d]', '', raw_price)
            price_int = int(digits) if digits else None
            if menu:
                d['menu_items'].append({'name': menu, 'price': price_int})
                if price_int:
                    d['prices'].append(price_int)

    result = []
    for i, d in enumerate(data.values()):
        txt = ' '.join(item['name'] for item in d['menu_items'])
        ps = d['prices']
        avg = sum(ps) / len(ps) if ps else 0
        result.append({
            'id': i,
            'name': d['name'],
            'address': d['address'],
            'open_time': d['open_time'],
            'menu_items': d['menu_items'],
            'min_price': min(ps) if ps else 0,
            'max_price': max(ps) if ps else 0,
            'avg_price': int(avg),
            'cuisines': detect_cuisine(txt),
            'themes': detect_themes(txt, avg),
        })
    return result


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                restaurant_name TEXT NOT NULL,
                author TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()


RESTAURANTS: list = []


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/restaurants')
def api_restaurants():
    return jsonify(RESTAURANTS)


@app.route('/api/random')
def api_random():
    cuisine = request.args.get('cuisine', '')
    theme = request.args.get('theme', '')
    pool = [r for r in RESTAURANTS
            if (not cuisine or cuisine in r['cuisines'])
            and (not theme or theme in r['themes'])]
    return jsonify(random.choice(pool or RESTAURANTS))


@app.route('/api/comments', methods=['GET'])
def get_comments():
    name = request.args.get('name', '')
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            'SELECT author, content, created_at FROM comments WHERE restaurant_name=? ORDER BY created_at DESC',
            (name,)
        ).fetchall()
    return jsonify([{'author': r[0], 'content': r[1], 'at': r[2][:16]} for r in rows])


@app.route('/api/comments', methods=['POST'])
def add_comment():
    body = request.get_json() or {}
    name = (body.get('restaurant_name') or '').strip()
    author = (body.get('author') or '익명').strip()[:20]
    content = (body.get('content') or '').strip()[:100]
    if not name or not content:
        return jsonify({'error': '입력값 오류'}), 400
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            'INSERT INTO comments (restaurant_name, author, content) VALUES (?,?,?)',
            (name, author, content)
        )
        conn.commit()
    return jsonify({'ok': True})


if __name__ == '__main__':
    init_db()
    RESTAURANTS = load_restaurants()
    print(f"[INFO] 식당 {len(RESTAURANTS)}개 로드 완료")
    app.run(debug=True, port=5000)
