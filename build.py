"""
CSV → data.json 변환 스크립트
lunch.py 실행 후 이 스크립트를 실행하면 data.json이 갱신됩니다.
"""
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

CSV_PATH = Path(__file__).parent / "naver_map_restaurants_menus.csv"
OUT_PATH = Path(__file__).parent / "data.json"

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
    '가벼운 한끼 🥗': ['샐러드', '샌드위치', '소바', '냉소바', '쌀국수', '김밥', '누들', '막국수', '오니기리'],
    '카페 ☕': ['에스프레소', '아메리카노', '카페라떼', '라떼', '마리또조', '크로아상', '커피', '아포가토', '콜드브루'],
}


def detect_cuisine(text):
    result = [c for c, kws in CUISINE_MAP.items() if any(k in text for k in kws)]
    return result or ['기타']


def detect_themes(text, avg):
    themes = [t for t, kws in THEME_MAP.items() if any(k in text for k in kws)]
    is_cafe = '카페 ☕' in themes
    if avg and avg < 10000 and not is_cafe:
        themes.append('가성비 👍')
    return themes


def main():
    data = defaultdict(lambda: {'name': '', 'address': '', 'open_time': '', 'menu_items': [], 'prices': []})

    with open(CSV_PATH, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            name = row.get('place_name', '').strip()
            if not name:
                continue
            d = data[name]
            d['name'] = name
            d['address'] = row.get('address', '').strip()
            d['open_time'] = row.get('open_time_text', '').strip()
            menu = row.get('menu_name', '').strip()
            raw = row.get('price') or row.get('price_krw') or row.get('price_raw') or ''
            digits = re.sub(r'[^\d]', '', raw)
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

    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"완료: {len(result)}개 식당 → {OUT_PATH}")


if __name__ == '__main__':
    main()
