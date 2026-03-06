"""
generate.py: CSV를 읽어서 데이터가 내장된 독립 실행 index.html을 생성합니다.
lunch.py 실행 후 이 스크립트를 한 번 실행하면, index.html을 더블클릭으로 바로 열 수 있습니다.
"""
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).parent
CSV_PATH = BASE_DIR / "naver_map_restaurants_menus.csv"
OUT_PATH = BASE_DIR / "index.html"

CUISINE_MAP = {
    '한식': ['김치','된장','비빔','냉면','삼겹','갈비','육개장','순두부','설렁탕','곰탕',
              '만두','전골','불고기','보쌈','족발','국밥','찌개','구이','제육','막회',
              '육회','수육','쌈','오징어','해물','고등어','갈치','순대','미나리',
              '굴','물회','갈비탕','꽃게','뚝배기','떡','전','회'],
    '중식': ['짜장','짬뽕','탕수육','마파두부','볶음밥','딤섬','교자','소롱포','탄탄면',
              '마라','쇼마이','기스면','팔진','하교','우육','사천','부추굴'],
    '일식': ['라멘','스시','초밥','돈까스','우동','소바','덴뿌라','야키','사시미',
              '규동','오마카세','편백','샤브샤브','규카츠','가츠'],
    '양식': ['파스타','피자','스테이크','버거','리조또','샌드위치','브런치',
              '에스프레소','와인','맥주','아이스크림','마리또조'],
}
THEME_MAP = {
    '해장용 🍜':      ['해장','국밥','설렁탕','육개장','순댓국','콩나물','순두부','곰탕','해장라면'],
    '든든한 한끼 🍱':  ['정식','백반','도시락','비빔밥','덮밥','볶음밥'],
    '고기 먹고 싶다 🥩': ['삼겹','갈비','목살','차돌','직화','소고기','한우','구이','불고기'],
    '면 생각날 때 🍝': ['냉면','우동','라멘','짬뽕','짜장','파스타','탄탄면','막국수','쫄면','소바'],
    '가벼운 한끼 🥗':  ['샐러드','샌드위치','소바','냉소바','쌀국수','김밥','누들','막국수','오니기리'],
    '카페 ☕':        ['에스프레소','아메리카노','카페라떼','라떼','마리또조','크로아상','커피','아포가토','콜드브루'],
}


def detect_cuisine(text):
    r = [c for c, kws in CUISINE_MAP.items() if any(k in text for k in kws)]
    return r or ['기타']


def detect_themes(text, avg):
    themes = [t for t, kws in THEME_MAP.items() if any(k in text for k in kws)]
    if avg and avg < 10000 and '카페 ☕' not in themes:
        themes.append('가성비 👍')
    return themes


def build_data():
    store = defaultdict(lambda: {'name':'','address':'','open_time':'','menu_items':[],'prices':[]})
    with open(CSV_PATH, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            name = row.get('place_name','').strip()
            if not name:
                continue
            d = store[name]
            d['name']      = name
            d['address']   = row.get('address','').strip()
            d['open_time'] = row.get('open_time_text','').strip()
            menu   = row.get('menu_name','').strip()
            raw    = row.get('price') or row.get('price_krw') or row.get('price_raw') or ''
            price  = int(re.sub(r'[^\d]','',raw)) if re.sub(r'[^\d]','',raw) else None
            if menu:
                d['menu_items'].append({'name': menu, 'price': price})
                if price:
                    d['prices'].append(price)

    result = []
    for i, d in enumerate(store.values()):
        txt = ' '.join(m['name'] for m in d['menu_items'])
        ps  = d['prices']
        avg = sum(ps)/len(ps) if ps else 0
        result.append({
            'id':        i,
            'name':      d['name'],
            'address':   d['address'],
            'open_time': d['open_time'],
            'menu_items': d['menu_items'],
            'min_price': min(ps) if ps else 0,
            'max_price': max(ps) if ps else 0,
            'avg_price': round(avg),
            'cuisines':  detect_cuisine(txt),
            'themes':    detect_themes(txt, avg),
        })
    return result


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>오늘 뭐 먹지? 🍽️</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg: #FFF0F6; --primary: #FF6B9D; --pink-light: #FFB3CC;
      --text: #2C2C2C; --muted: #AAA; --card: #fff;
      --border: #F5D6E8; --radius: 16px; --shadow: 0 4px 20px rgba(255,107,157,0.1);
    }
    body { font-family: 'Noto Sans KR', sans-serif; background: linear-gradient(150deg, #FFE8F3 0%, #F8E6FF 40%, #EAE8FF 75%, #E8F2FF 100%) fixed; color: var(--text); min-height: 100vh; }
    header { background: linear-gradient(150deg, #FFF5F9 0%, #FFE0EF 45%, #F8D4F4 100%); color: #C0578A; padding: 24px 24px 0; text-align: center; }
    .header-title { font-size: 30px; font-weight: 900; letter-spacing: -1px; }
    .header-sub   { font-size: 14px; opacity: 0.7; margin-top: 4px; }
    .random-section { background: linear-gradient(150deg, #FFF5F9 0%, #FFE0EF 45%, #F8D4F4 100%); padding: 20px 24px 36px; display: flex; flex-direction: column; align-items: center; gap: 16px; }
    .random-label { color: #C0578A; font-size: 17px; font-weight: 700; }
    .random-quick-filters { display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; }
    .qf-chip { background: rgba(255,255,255,0.65); color: #C0578A; border: 1.5px solid rgba(192,87,138,0.25); border-radius: 20px; padding: 6px 16px; font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.18s; font-family: inherit; }
    .qf-chip:hover, .qf-chip.active { background: #C0578A; color: white; border-color: #C0578A; }
    .random-card-wrap { width: 100%; max-width: 460px; }
    .random-card { background: white; border-radius: 22px; padding: 28px 24px; box-shadow: 0 12px 40px rgba(255,107,157,0.25); min-height: 200px; display: flex; align-items: center; justify-content: center; }
    .random-placeholder { text-align: center; color: #dbb8c8; }
    .random-placeholder .big-emoji { font-size: 52px; margin-bottom: 10px; }
    .random-placeholder p { font-size: 15px; }
    .random-loading { text-align: center; }
    .shake-emoji { font-size: 52px; display: inline-block; animation: shakeIt 0.5s ease-in-out infinite; }
    .loading-text { font-size: 15px; color: var(--muted); margin-top: 10px; }
    @keyframes shakeIt { 0%,100%{transform:rotate(0deg) scale(1)} 20%{transform:rotate(-10deg) scale(1.08)} 40%{transform:rotate(10deg) scale(1.08)} 60%{transform:rotate(-7deg) scale(1.12)} 80%{transform:rotate(7deg) scale(1.12)} }
    .random-result { width: 100%; }
    .result-ticket-label { font-size: 11px; font-weight: 700; color: var(--primary); letter-spacing: 1px; text-align: center; margin-bottom: 12px; display: flex; align-items: center; justify-content: center; gap: 5px; }
    .result-ticket-label::before { content:''; flex:1; height:1px; background:linear-gradient(to right,transparent,#FFB3CC); }
    .result-ticket-label::after  { content:''; flex:1; height:1px; background:linear-gradient(to left, transparent,#FFB3CC); }
    .random-result .r-emoji { font-size: 44px; text-align: center; display: block; margin-bottom: 10px; }
    .random-result .r-name  { font-size: 22px; font-weight: 900; text-align: center; margin-bottom: 10px; line-height: 1.3; }
    .random-result .r-badges { display: flex; gap: 6px; flex-wrap: wrap; justify-content: center; margin-bottom: 12px; }
    .random-result .r-menus-preview { font-size: 13px; color: var(--muted); text-align: center; margin-bottom: 8px; line-height: 1.6; }
    .random-result .r-price { font-size: 15px; font-weight: 700; text-align: center; color: var(--primary); margin-bottom: 16px; }
    .random-result .go-btn { display: block; width: 100%; background: linear-gradient(135deg,#FF6B9D,#FFA8CA); color: white; border: none; border-radius: 12px; padding: 12px; font-size: 15px; font-weight: 700; cursor: pointer; font-family: inherit; transition: opacity 0.15s,transform 0.15s; }
    .random-result .go-btn:hover { opacity: 0.88; transform: scale(1.02); }
    @keyframes ticketUnroll { 0%{transform:scaleY(0) rotate(-2deg);transform-origin:top center;opacity:0} 55%{transform:scaleY(1.05) rotate(1deg);transform-origin:top center;opacity:1} 75%{transform:scaleY(0.97) rotate(-0.5deg);transform-origin:top center} 100%{transform:scaleY(1) rotate(0deg);transform-origin:top center;opacity:1} }
    .ticket-unroll { animation: ticketUnroll 0.6s cubic-bezier(0.34,1.4,0.64,1); }
    .pick-btn { background: white; color: var(--primary); border: none; border-radius: 50px; padding: 15px 44px; font-size: 17px; font-weight: 900; cursor: pointer; font-family: inherit; box-shadow: 0 6px 24px rgba(255,107,157,0.3); transition: transform 0.15s,box-shadow 0.15s; letter-spacing: -0.3px; }
    .pick-btn:hover { transform: scale(1.06); box-shadow: 0 8px 30px rgba(255,107,157,0.4); }
    .pick-btn:active { transform: scale(0.97); }
    .pick-btn:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
    @keyframes btnBounce { 0%,100%{transform:scale(1)} 30%{transform:scale(0.93)} 65%{transform:scale(1.07)} }
    .pick-btn.bouncing { animation: btnBounce 0.35s ease; }
    .filter-section { background: white; padding: 16px 20px; border-bottom: 1px solid var(--border); position: sticky; top: 0; z-index: 10; box-shadow: 0 2px 12px rgba(255,107,157,0.08); }
    .search-bar { display: flex; align-items: center; background: var(--bg); border: 1.5px solid var(--border); border-radius: 12px; padding: 0 14px; margin-bottom: 12px; }
    .search-bar input { flex: 1; border: none; background: none; padding: 11px 8px; font-size: 15px; font-family: inherit; color: var(--text); outline: none; }
    .search-icon { font-size: 17px; color: var(--muted); }
    .filter-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; overflow-x: auto; scrollbar-width: none; }
    .filter-row:last-child { margin-bottom: 0; }
    .filter-row::-webkit-scrollbar { display: none; }
    .filter-label { font-size: 11px; font-weight: 700; color: var(--muted); white-space: nowrap; min-width: 48px; }
    .chip { border: 1.5px solid var(--border); border-radius: 20px; padding: 5px 14px; font-size: 13px; font-weight: 500; cursor: pointer; white-space: nowrap; transition: all 0.18s; font-family: inherit; background: white; color: var(--text); }
    .chip:hover { border-color: var(--primary); color: var(--primary); }
    .chip.active { background: var(--primary); border-color: var(--primary); color: white; }
    .cards-section { padding: 20px 20px 60px; max-width: 1200px; margin: 0 auto; }
    .cards-count { font-size: 14px; color: var(--muted); font-weight: 500; margin-bottom: 16px; }
    .cards-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px,1fr)); gap: 16px; }
    .r-card { background: var(--card); border-radius: var(--radius); padding: 20px; box-shadow: var(--shadow); cursor: pointer; transition: transform 0.2s,box-shadow 0.2s; border: 1.5px solid transparent; position: relative; overflow: hidden; }
    .r-card::before { content:''; position:absolute; top:0; left:0; width:5px; height:100%; background:var(--accent-color,var(--primary)); }
    .r-card:hover { transform: translateY(-4px); box-shadow: 0 10px 36px rgba(255,107,157,0.15); }
    .card-top { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 10px; }
    .card-emoji { font-size: 28px; flex-shrink: 0; }
    .card-name  { font-size: 15px; font-weight: 700; line-height: 1.35; flex: 1; }
    .card-badges { display: flex; gap: 5px; flex-wrap: wrap; margin-bottom: 10px; }
    .badge { font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 6px; white-space: nowrap; }
    .badge-한식  { background:#FFF0E6; color:#D45E1A; }
    .badge-중식  { background:#FFE6F0; color:#B5174E; }
    .badge-일식  { background:#E6F0FF; color:#1053C4; }
    .badge-양식  { background:#E6F5EA; color:#1E7A34; }
    .badge-기타  { background:#F5F0FF; color:#6B48BF; }
    .badge-theme { background:#FFF0F6; color:#C94080; }
    .card-menus { font-size: 13px; color: var(--muted); margin-bottom: 10px; line-height: 1.6; }
    .card-menus span+span::before { content:' · '; color:#F5C0D5; }
    .card-price { font-size: 14px; font-weight: 700; color: var(--primary); }
    .empty-state { text-align: center; padding: 60px 20px; color: var(--muted); grid-column: 1/-1; }
    .empty-emoji { font-size: 48px; margin-bottom: 12px; }
    .modal-overlay { position: fixed; inset: 0; background: rgba(180,60,100,0.25); z-index: 100; display: none; align-items: center; justify-content: center; padding: 20px; backdrop-filter: blur(3px); }
    .modal-overlay.show { display: flex; }
    .modal { background: white; border-radius: 24px; width: 100%; max-width: 520px; max-height: 90vh; overflow-y: auto; position: relative; animation: modalIn 0.32s cubic-bezier(0.34,1.3,0.64,1); }
    @keyframes modalIn { from{transform:translateY(40px) scale(0.95);opacity:0} to{transform:translateY(0) scale(1);opacity:1} }
    .modal-close { position: sticky; top: 14px; float: right; margin: 14px 14px 0 0; background: #FFF0F6; border: none; border-radius: 50%; width: 36px; height: 36px; font-size: 18px; cursor: pointer; display: flex; align-items: center; justify-content: center; color: var(--primary); z-index: 1; transition: background 0.15s; font-family: inherit; }
    .modal-close:hover { background: #FFD6E8; }
    .modal-header { padding: 20px 24px 0; clear: both; }
    .modal-c-emoji { font-size: 40px; margin-bottom: 8px; }
    .modal-name    { font-size: 22px; font-weight: 900; margin-bottom: 10px; line-height: 1.3; }
    .modal-badges  { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 14px; }
    .modal-info    { display: flex; flex-direction: column; gap: 6px; margin-bottom: 20px; }
    .modal-info-item { font-size: 14px; color: #666; display: flex; align-items: flex-start; gap: 7px; line-height: 1.5; }
    .info-icon { flex-shrink: 0; font-size: 15px; }
    .modal-divider { height: 1px; background: var(--border); margin: 0 24px; }
    .modal-body { padding: 20px 24px 28px; }
    .section-title { font-size: 16px; font-weight: 700; margin-bottom: 12px; }
    .menu-list { display: flex; flex-direction: column; gap: 7px; margin-bottom: 24px; max-height: 260px; overflow-y: auto; }
    .menu-item { display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; background: var(--bg); border-radius: 10px; font-size: 14px; }
    .m-name  { font-weight: 500; }
    .m-price { font-weight: 700; color: var(--primary); white-space: nowrap; margin-left: 12px; }
    .comments-list { display: flex; flex-direction: column; gap: 10px; margin-bottom: 16px; }
    .comment-item { background: var(--bg); border-radius: 12px; padding: 12px 14px; }
    .comment-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px; }
    .comment-author { font-size: 13px; font-weight: 700; display: flex; align-items: center; gap: 7px; }
    .comment-avatar { width: 24px; height: 24px; border-radius: 50%; color: white; font-size: 11px; font-weight: 700; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
    .comment-at { font-size: 11px; color: var(--muted); }
    .comment-content { font-size: 14px; color: #444; line-height: 1.55; }
    .no-comments { text-align: center; padding: 20px; color: var(--muted); font-size: 14px; }
    .comment-form { background: var(--bg); border-radius: 14px; padding: 14px; display: flex; flex-direction: column; gap: 8px; }
    .comment-form input, .comment-form textarea { border: 1.5px solid var(--border); border-radius: 10px; padding: 10px 12px; font-size: 14px; font-family: inherit; background: white; color: var(--text); outline: none; width: 100%; transition: border-color 0.2s; }
    .comment-form input:focus, .comment-form textarea:focus { border-color: var(--primary); }
    .comment-form textarea { resize: none; height: 72px; }
    .comment-submit { background: linear-gradient(135deg,#FF6B9D,#FFA8CA); color: white; border: none; border-radius: 10px; padding: 11px; font-size: 14px; font-weight: 700; cursor: pointer; font-family: inherit; transition: opacity 0.15s; }
    .comment-submit:hover { opacity: 0.88; }
    .comment-submit:disabled { opacity: 0.5; cursor: not-allowed; }
    @media (max-width: 600px) { .cards-grid{grid-template-columns:1fr} .modal{border-radius:20px 20px 0 0;max-height:95vh} .modal-overlay{align-items:flex-end;padding:0} }
  </style>
</head>
<body>
<header>
  <div class="header-title">🍽️ 오늘 뭐 먹지?</div>
  <div class="header-sub">역삼역 점심 메뉴 고민 해결사</div>
</header>
<section class="random-section">
  <div class="random-label">✨ 오늘의 메뉴 뽑기</div>
  <div class="random-quick-filters" id="random-filters">
    <button class="qf-chip active" data-val="">전체</button>
    <button class="qf-chip" data-val="한식">🍚 한식</button>
    <button class="qf-chip" data-val="중식">🥢 중식</button>
    <button class="qf-chip" data-val="일식">🍱 일식</button>
    <button class="qf-chip" data-val="양식">🍝 양식</button>
  </div>
  <div class="random-card-wrap">
    <div class="random-card" id="random-card">
      <div class="random-placeholder">
        <div class="big-emoji">🎟️</div>
        <p>버튼을 눌러 오늘의 메뉴를 뽑아보세요!</p>
      </div>
    </div>
  </div>
  <button class="pick-btn" id="pick-btn" onclick="pickRandom()">오늘은 이거다! 🎟️</button>
</section>
<div class="filter-section">
  <div class="search-bar">
    <span class="search-icon">🔍</span>
    <input type="text" id="search-input" placeholder="식당 이름으로 검색..." oninput="applyFilters()">
  </div>
  <div class="filter-row">
    <span class="filter-label">종류</span>
    <button class="chip active" data-g="cuisine" data-val="" onclick="setCuisine('')">전체</button>
    <button class="chip" data-g="cuisine" data-val="한식" onclick="setCuisine('한식')">🍚 한식</button>
    <button class="chip" data-g="cuisine" data-val="중식" onclick="setCuisine('중식')">🥢 중식</button>
    <button class="chip" data-g="cuisine" data-val="일식" onclick="setCuisine('일식')">🍱 일식</button>
    <button class="chip" data-g="cuisine" data-val="양식" onclick="setCuisine('양식')">🍝 양식</button>
    <button class="chip" data-g="cuisine" data-val="기타" onclick="setCuisine('기타')">🍽️ 기타</button>
  </div>
  <div class="filter-row">
    <span class="filter-label">테마</span>
    <button class="chip active" data-g="theme" data-val="" onclick="setTheme('')">전체</button>
    <button class="chip" data-g="theme" data-val="해장용 🍜" onclick="setTheme('해장용 🍜')">해장용 🍜</button>
    <button class="chip" data-g="theme" data-val="든든한 한끼 🍱" onclick="setTheme('든든한 한끼 🍱')">든든한 한끼 🍱</button>
    <button class="chip" data-g="theme" data-val="고기 먹고 싶다 🥩" onclick="setTheme('고기 먹고 싶다 🥩')">고기 먹고 싶다 🥩</button>
    <button class="chip" data-g="theme" data-val="면 생각날 때 🍝" onclick="setTheme('면 생각날 때 🍝')">면 생각날 때 🍝</button>
    <button class="chip" data-g="theme" data-val="가벼운 한끼 🥗" onclick="setTheme('가벼운 한끼 🥗')">가벼운 한끼 🥗</button>
    <button class="chip" data-g="theme" data-val="카페 ☕" onclick="setTheme('카페 ☕')">카페 ☕</button>
    <button class="chip" data-g="theme" data-val="가성비 👍" onclick="setTheme('가성비 👍')">가성비 👍</button>
  </div>
</div>
<section class="cards-section">
  <div class="cards-count" id="cards-count"></div>
  <div class="cards-grid" id="cards-grid"></div>
</section>
<div class="modal-overlay" id="modal-overlay" onclick="onOverlayClick(event)">
  <div class="modal" id="modal">
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-header">
      <div class="modal-c-emoji" id="modal-emoji"></div>
      <div class="modal-name"   id="modal-name"></div>
      <div class="modal-badges" id="modal-badges"></div>
      <div class="modal-info"   id="modal-info"></div>
    </div>
    <div class="modal-divider"></div>
    <div class="modal-body">
      <div class="section-title">📋 메뉴</div>
      <div class="menu-list" id="modal-menus"></div>
      <div class="section-title">💬 한 줄 소감</div>
      <div class="comments-list" id="comments-list"></div>
      <div class="comment-form">
        <input type="text" id="c-author" placeholder="닉네임 (최대 20자)" maxlength="20">
        <textarea id="c-content" placeholder="오늘 점심 어땠나요? 한 줄 소감 남겨보기 ✍️ (최대 100자)" maxlength="100"></textarea>
        <button class="comment-submit" onclick="submitComment()">소감 남기기 ✍️</button>
      </div>
    </div>
  </div>
</div>
<script>
const RESTAURANTS = __DATA__;

const CUISINE_EMOJI  = {'한식':'🍚','중식':'🥢','일식':'🍱','양식':'🍝','기타':'🍽️'};
const CUISINE_ACCENT = {'한식':'#FF8C42','중식':'#FF5C8D','일식':'#5B8FF9','양식':'#5AD8A6','기타':'#C77DFF'};
const AVATAR_COLORS  = ['#FF6B9D','#4ECDC4','#FFD166','#C77DFF','#FF9B53','#5B8FF9'];
const STORAGE_KEY    = 'lunchbreak_comments';

let allRestaurants    = RESTAURANTS;
let filteredRestaurants = RESTAURANTS;
let selectedCuisine   = '';
let selectedTheme     = '';
let randomCuisine     = '';
let currentRestaurant = null;

function fmt(p)   { return p ? p.toLocaleString('ko-KR')+'원' : ''; }
function priceRange(r) {
  if (!r.min_price && !r.max_price) return '가격 정보 없음';
  if (r.min_price === r.max_price)  return fmt(r.min_price);
  return fmt(r.min_price)+' ~ '+fmt(r.max_price);
}
function cEmoji(r) { return CUISINE_EMOJI[r.cuisines[0]] || '🍽️'; }
function esc(s)    { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function badgesHTML(r) {
  return r.cuisines.map(c=>`<span class="badge badge-${c}">${c}</span>`).join('')
       + r.themes.slice(0,2).map(t=>`<span class="badge badge-theme">${t}</span>`).join('');
}

function loadAllComments()  { try{return JSON.parse(localStorage.getItem(STORAGE_KEY)||'{}')}catch{return{}} }
function getComments(name)  { return (loadAllComments()[name]||[]).slice().reverse(); }
function addComment(name, author, content) {
  const all = loadAllComments();
  if (!all[name]) all[name]=[];
  all[name].push({author,content,at:new Date().toISOString().slice(0,16).replace('T',' ')});
  localStorage.setItem(STORAGE_KEY,JSON.stringify(all));
}

function cardHTML(r) {
  const accent  = CUISINE_ACCENT[r.cuisines[0]] || '#FF6B9D';
  const preview = r.menu_items.slice(0,3).map(m=>`<span>${esc(m.name)}</span>`).join('');
  return `<div class="r-card" style="--accent-color:${accent}" onclick="openModal(${r.id})">
    <div class="card-top"><span class="card-emoji">${cEmoji(r)}</span><span class="card-name">${esc(r.name)}</span></div>
    <div class="card-badges">${badgesHTML(r)}</div>
    ${preview?`<div class="card-menus">${preview}</div>`:''}
    <div class="card-price">${priceRange(r)}</div>
  </div>`;
}
function renderCards() {
  const grid=document.getElementById('cards-grid'), count=document.getElementById('cards-count');
  if(!filteredRestaurants.length){grid.innerHTML='<div class="empty-state"><div class="empty-emoji">😅</div><p>해당 조건의 식당이 없어요!</p></div>';count.textContent='';return;}
  count.textContent=`총 ${filteredRestaurants.length}개 식당`;
  grid.innerHTML=filteredRestaurants.map(cardHTML).join('');
}

function applyFilters() {
  const q=document.getElementById('search-input').value.trim();
  filteredRestaurants=allRestaurants.filter(r=>(!selectedCuisine||r.cuisines.includes(selectedCuisine))&&(!selectedTheme||r.themes.includes(selectedTheme))&&(!q||r.name.includes(q)));
  renderCards();
}
function setCuisine(val){selectedCuisine=val;document.querySelectorAll('[data-g="cuisine"]').forEach(c=>c.classList.toggle('active',c.dataset.val===val));applyFilters();}
function setTheme(val)  {selectedTheme=val;document.querySelectorAll('[data-g="theme"]').forEach(c=>c.classList.toggle('active',c.dataset.val===val));applyFilters();}
function setRandomCuisine(val){randomCuisine=val;document.querySelectorAll('#random-filters .qf-chip').forEach(c=>c.classList.toggle('active',c.dataset.val===val));}

function pickRandom() {
  if(!allRestaurants.length) return;
  const btn=document.getElementById('pick-btn'), card=document.getElementById('random-card');
  btn.disabled=true; btn.classList.add('bouncing');
  btn.addEventListener('animationend',()=>btn.classList.remove('bouncing'),{once:true});
  card.innerHTML='<div class="random-loading"><span class="shake-emoji">🎟️</span><div class="loading-text">뽑는 중~</div></div>';
  setTimeout(()=>{
    const pool=allRestaurants.filter(r=>!randomCuisine||r.cuisines.includes(randomCuisine));
    const r=pool[Math.floor(Math.random()*pool.length)];
    const prev=r.menu_items.slice(0,3).map(m=>esc(m.name)).join(' · ')||'-';
    card.innerHTML=`<div class="random-result ticket-unroll">
      <div class="result-ticket-label">🎟️ 오늘의 선택</div>
      <span class="r-emoji">${cEmoji(r)}</span>
      <div class="r-name">${esc(r.name)}</div>
      <div class="r-badges">${badgesHTML(r)}</div>
      <div class="r-menus-preview">${prev}</div>
      <div class="r-price">${priceRange(r)}</div>
      <button class="go-btn" onclick="openModal(${r.id})">자세히 보기 →</button>
    </div>`;
    btn.disabled=false; btn.textContent='다시 뽑기! 🎟️';
  },700);
}

function openModal(id) {
  const r=allRestaurants.find(x=>x.id===id); if(!r) return;
  currentRestaurant=r;
  document.getElementById('modal-emoji').textContent=cEmoji(r);
  document.getElementById('modal-name').textContent=r.name;
  document.getElementById('modal-badges').innerHTML=badgesHTML(r);
  let info='';
  if(r.address)   info+=`<div class="modal-info-item"><span class="info-icon">📍</span><span>${esc(r.address)}</span></div>`;
  if(r.open_time) info+=`<div class="modal-info-item"><span class="info-icon">🕐</span><span>${esc(r.open_time)}</span></div>`;
  document.getElementById('modal-info').innerHTML=info;
  const menus=document.getElementById('modal-menus');
  menus.innerHTML=r.menu_items.length
    ?r.menu_items.map(m=>`<div class="menu-item"><span class="m-name">${esc(m.name)}</span>${m.price?`<span class="m-price">${m.price.toLocaleString('ko-KR')}원</span>`:''}</div>`).join('')
    :'<div class="no-comments">메뉴 정보가 없어요 😅</div>';
  renderComments(r.name);
  document.getElementById('c-author').value=''; document.getElementById('c-content').value='';
  document.getElementById('modal-overlay').classList.add('show'); document.body.style.overflow='hidden';
}
function closeModal(){document.getElementById('modal-overlay').classList.remove('show');document.body.style.overflow='';currentRestaurant=null;}
function onOverlayClick(e){if(e.target===document.getElementById('modal-overlay'))closeModal();}

function renderComments(name) {
  const list=document.getElementById('comments-list'), comments=getComments(name);
  if(!comments.length){list.innerHTML='<div class="no-comments">첫 번째 소감을 남겨보세요! 🌟</div>';return;}
  list.innerHTML=comments.map(c=>{
    const color=AVATAR_COLORS[c.author.charCodeAt(0)%AVATAR_COLORS.length];
    return `<div class="comment-item"><div class="comment-header"><div class="comment-author"><div class="comment-avatar" style="background:${color}">${esc(c.author.charAt(0))}</div>${esc(c.author)}</div><div class="comment-at">${c.at}</div></div><div class="comment-content">${esc(c.content)}</div></div>`;
  }).join('');
}
function submitComment() {
  if(!currentRestaurant) return;
  const author=document.getElementById('c-author').value.trim()||'익명';
  const content=document.getElementById('c-content').value.trim();
  if(!content){alert('소감을 입력해주세요!');return;}
  addComment(currentRestaurant.name,author,content);
  document.getElementById('c-author').value=''; document.getElementById('c-content').value='';
  renderComments(currentRestaurant.name);
}

document.querySelectorAll('#random-filters .qf-chip').forEach(chip=>chip.addEventListener('click',()=>setRandomCuisine(chip.dataset.val)));
renderCards();
</script>
</body>
</html>"""


def main():
    data = build_data()
    data_json = json.dumps(data, ensure_ascii=False)
    html = HTML_TEMPLATE.replace('__DATA__', data_json)
    OUT_PATH.write_text(html, encoding='utf-8')
    print(f"완료: {len(data)}개 식당 → {OUT_PATH}")
    print("index.html을 더블클릭으로 바로 열 수 있습니다!")


if __name__ == '__main__':
    main()
