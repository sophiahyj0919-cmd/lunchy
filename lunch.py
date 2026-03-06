import csv
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from playwright.sync_api import sync_playwright

START_URL = "https://map.naver.com/p/search/%EC%97%AD%EC%82%BC%EC%97%AD%20%EC%9D%8C%EC%8B%9D%EC%A0%90?c=15.00,0,0,0,dh"
OUT_CSV = Path("naver_map_restaurants_menus.csv")

SCROLL_PAUSE_MS = 650
CLICK_PAUSE_MS = 850
DETAIL_LOAD_TIMEOUT_MS = 9000
MENU_LOAD_TIMEOUT_MS = 9000

# 페이지 내 스크롤 끝 판정(새 식당명 증가가 이 횟수만큼 연속 0이면 종료)
NO_GROWTH_LIMIT = 10

# 메뉴 더보기(펼쳐서 더보기) 반복 클릭 최대 횟수
MAX_MORE_CLICKS = 20

# 한 페이지에서 식당을 처리할 때, "현재 화면에 렌더링된 것들"을 여러 라운드로 처리
# (스크롤로 더 로드되면 다시 처리)
MAX_PROCESS_ROUNDS_PER_PAGE = 60


def clean_price_to_int(text: str) -> Optional[int]:
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def safe_inner_text(locator) -> str:
    try:
        return locator.first.inner_text().strip()
    except Exception:
        return ""


def get_frames(page):
    search_frame = None
    entry_frame = None
    for f in page.frames:
        if f.name == "searchIframe":
            search_frame = f
        elif f.name == "entryIframe":
            entry_frame = f
    return search_frame, entry_frame


def wait_for_search_iframe(page, timeout_ms=15000):
    start = time.time()
    while (time.time() - start) * 1000 < timeout_ms:
        search_frame, _ = get_frames(page)
        if search_frame:
            return search_frame
        page.wait_for_timeout(300)
    raise RuntimeError("searchIframe을 찾지 못했습니다.")


def wait_for_entry_iframe(page, timeout_ms=15000):
    start = time.time()
    while (time.time() - start) * 1000 < timeout_ms:
        _, entry_frame = get_frames(page)
        if entry_frame:
            return entry_frame
        page.wait_for_timeout(300)
    raise RuntimeError("entryIframe을 찾지 못했습니다.")


def append_rows_to_csv(path: Path, rows: List[Dict]):
    is_new = not path.exists()
    with path.open("a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["page_num", "place_name", "address", "open_time_text", "menu_name", "price_krw", "price_raw"],
        )
        if is_new:
            w.writeheader()
        for r in rows:
            w.writerow(r)


def get_total_pages(search_frame, fallback: int = 5) -> int:
    """
    <a class="mBN2s">2</a> 같은 페이지 버튼을 읽어 최대 페이지 숫자 추정
    """
    try:
        btns = search_frame.locator("a.mBN2s")
        cnt = btns.count()
        mx = 1
        for i in range(cnt):
            t = safe_inner_text(btns.nth(i))
            if t.isdigit():
                mx = max(mx, int(t))
        return mx if mx >= 1 else fallback
    except Exception:
        return fallback


def go_to_page(search_frame, page_num: int) -> bool:
    """
    페이지네이션 클릭
    """
    search_frame.page.wait_for_timeout(500)

    btn = search_frame.locator("a.mBN2s", has_text=str(page_num))
    if btn.count() == 0:
        btn = search_frame.locator("a", has_text=str(page_num))
    if btn.count() == 0:
        return False

    try:
        btn.first.scroll_into_view_if_needed()
        btn.first.click()
        search_frame.page.wait_for_timeout(1200)
        return True
    except Exception:
        return False


def scroll_page_results_to_end(search_frame) -> None:
    """
    현재 페이지의 검색결과 리스트를 끝까지 스크롤해서 최대한 로드
    (새 TYaxT 이름 증가가 일정 횟수 연속 0이면 종료)
    """
    seen = set()
    no_growth = 0

    scroll_candidates = [
        "div#_pcmap_list_scroll_container",
        "div[role='main']",
        "div:has(span.TYaxT)",
        "body",
    ]

    while True:
        names = []
        loc = search_frame.locator("span.TYaxT")
        cnt = loc.count()
        for i in range(cnt):
            try:
                t = loc.nth(i).inner_text().strip()
                if t:
                    names.append(t)
            except Exception:
                continue

        new_added = 0
        for n in names:
            if n not in seen:
                seen.add(n)
                new_added += 1

        if new_added == 0:
            no_growth += 1
        else:
            no_growth = 0

        if no_growth >= NO_GROWTH_LIMIT:
            break

        scrolled = False
        for sel in scroll_candidates:
            try:
                box = search_frame.locator(sel).first
                if box.count() > 0:
                    box.evaluate("(el) => { el.scrollBy(0, 1400); }")
                    scrolled = True
                    break
            except Exception:
                pass

        if not scrolled:
            try:
                search_frame.mouse.wheel(0, 1400)
            except Exception:
                pass

        search_frame.page.wait_for_timeout(SCROLL_PAUSE_MS)


def extract_address(entry_frame) -> str:
    try:
        entry_frame.wait_for_selector("span.pz7wy", timeout=DETAIL_LOAD_TIMEOUT_MS)
        return entry_frame.locator("span.pz7wy").first.inner_text().strip()
    except Exception:
        return ""


def extract_time_texts(entry_frame) -> str:
    try:
        time_locs = entry_frame.locator("time[aria-hidden='true']")
        cnt = time_locs.count()
        texts = []
        for i in range(min(cnt, 10)):
            t = safe_inner_text(time_locs.nth(i))
            if t:
                texts.append(t)
        return " | ".join(texts)
    except Exception:
        return ""


def click_menu_tab(entry_frame) -> bool:
    try:
        tab = entry_frame.locator(":is(a,button,div,span) span.I2hj8", has_text="메뉴")
        if tab.count() > 0:
            tab.first.click()
            return True
    except Exception:
        pass
    try:
        entry_frame.locator(":text('메뉴')").first.click()
        return True
    except Exception:
        return False


def click_all_more_buttons(entry_frame) -> int:
    clicks = 0
    for _ in range(MAX_MORE_CLICKS):
        more = entry_frame.locator("a.fvwqf:has(span.TeItc)", has_text="펼쳐서 더보기")
        if more.count() == 0:
            more = entry_frame.locator("a[role='button']", has_text="펼쳐서 더보기")
        if more.count() == 0:
            break

        try:
            more.first.scroll_into_view_if_needed()
            more.first.click()
            clicks += 1
            entry_frame.wait_for_timeout(650)
        except Exception:
            try:
                entry_frame.mouse.wheel(0, 900)
                entry_frame.wait_for_timeout(350)
            except Exception:
                pass
    return clicks


def load_all_menus(entry_frame) -> None:
    click_all_more_buttons(entry_frame)

    # 스크롤 로딩 유도
    prev_cnt = -1
    stable = 0
    for _ in range(18):
        try:
            cnt = entry_frame.locator("span.lPzHi").count()
        except Exception:
            cnt = 0

        if cnt == prev_cnt:
            stable += 1
        else:
            stable = 0
            prev_cnt = cnt

        if stable >= 4:
            break

        try:
            entry_frame.mouse.wheel(0, 1400)
        except Exception:
            pass
        entry_frame.wait_for_timeout(450)

    # 스크롤 후 더보기 다시 생길 수 있어 한 번 더
    click_all_more_buttons(entry_frame)


def extract_menu_pairs(entry_frame) -> List[Tuple[str, Optional[int], str]]:
    names = entry_frame.locator("span.lPzHi")
    prices = entry_frame.locator("span.p2H02 em")

    n_names = names.count()
    n_prices = prices.count()
    n = min(n_names, n_prices)

    out = []
    for i in range(n):
        menu_name = safe_inner_text(names.nth(i))
        price_raw = safe_inner_text(prices.nth(i))
        if not menu_name:
            continue
        out.append((menu_name, clean_price_to_int(price_raw), price_raw))

    # 가격 매칭이 0이면 메뉴명만이라도
    if not out and n_names > 0:
        for i in range(n_names):
            menu_name = safe_inner_text(names.nth(i))
            if menu_name:
                out.append((menu_name, None, ""))

    return out


def process_visible_restaurants_once(page, search_frame, page_num: int, processed: Set[str]) -> int:
    """
    현재 DOM에 '보이는/렌더링된' 식당들(span.TYaxT)을 위에서부터 순회하며
    아직 처리 안 한 식당은 클릭해서 상세/메뉴를 긁고 CSV 저장.
    처리한 개수 반환.
    """
    # 현재 렌더링된 식당명 리스트
    name_locs = search_frame.locator("span.TYaxT")
    cnt = name_locs.count()

    newly_processed = 0

    for i in range(cnt):
        place_name = ""
        try:
            place_name = name_locs.nth(i).inner_text().strip()
        except Exception:
            continue

        if not place_name or place_name in processed:
            continue

        # 클릭
        try:
            name_locs.nth(i).scroll_into_view_if_needed()
            name_locs.nth(i).click()
            page.wait_for_timeout(CLICK_PAUSE_MS)
        except Exception:
            continue

        # entryIframe
        try:
            entry_frame = wait_for_entry_iframe(page, timeout_ms=12000)
        except Exception:
            # 실패해도 processed 표시 안 하고 넘어가면 다음 라운드에 다시 시도 가능
            continue

        try:
            address = extract_address(entry_frame)
            open_time_text = extract_time_texts(entry_frame)

            # 메뉴 탭
            if not click_menu_tab(entry_frame):
                append_rows_to_csv(OUT_CSV, [{
                    "page_num": page_num,
                    "place_name": place_name,
                    "address": address,
                    "open_time_text": open_time_text,
                    "menu_name": "",
                    "price_krw": None,
                    "price_raw": "",
                }])
                processed.add(place_name)
                newly_processed += 1
                continue

            # 메뉴 로딩 대기
            try:
                entry_frame.wait_for_selector("span.lPzHi", timeout=MENU_LOAD_TIMEOUT_MS)
            except Exception:
                append_rows_to_csv(OUT_CSV, [{
                    "page_num": page_num,
                    "place_name": place_name,
                    "address": address,
                    "open_time_text": open_time_text,
                    "menu_name": "",
                    "price_krw": None,
                    "price_raw": "",
                }])
                processed.add(place_name)
                newly_processed += 1
                continue

            # 더보기/스크롤로 메뉴 최대 로딩
            load_all_menus(entry_frame)

            # 메뉴 화면에서 time이 더 잘 잡히는 경우 보강
            if not open_time_text:
                open_time_text = extract_time_texts(entry_frame)

            menu_pairs = extract_menu_pairs(entry_frame)

            rows = []
            if menu_pairs:
                for (menu_name, price_int, price_raw) in menu_pairs:
                    rows.append({
                        "page_num": page_num,
                        "place_name": place_name,
                        "address": address,
                        "open_time_text": open_time_text,
                        "menu_name": menu_name,
                        "price_krw": price_int,
                        "price_raw": price_raw,
                    })
            else:
                rows.append({
                    "page_num": page_num,
                    "place_name": place_name,
                    "address": address,
                    "open_time_text": open_time_text,
                    "menu_name": "",
                    "price_krw": None,
                    "price_raw": "",
                })

            append_rows_to_csv(OUT_CSV, rows)

            processed.add(place_name)
            newly_processed += 1

        except Exception as e:
            # Frame detached 등 예기치 않은 오류 → 이 식당은 processed에 추가하지 않고 넘어감
            print(f"  [WARN] '{place_name}' 처리 중 오류 (건너뜀): {e}")
            continue

        # 템포 유지(너무 빠르면 실패/차단 늘어남)
        page.wait_for_timeout(550)

    return newly_processed


def process_one_page_fully(page, search_frame, page_num: int) -> int:
    """
    ✅ 요청하신 핵심:
    '해당 페이지에서 스크롤로 식당들을 최대 로드한 뒤,
     그 페이지에 있는 식당들을 하나하나 눌러서 전부 처리'
    """
    print(f"\n[PAGE {page_num}] 1) 스크롤로 결과 최대 로드...")
    scroll_page_results_to_end(search_frame)

    processed: Set[str] = set()
    total_processed = 0

    print(f"[PAGE {page_num}] 2) 로드된 식당들을 하나씩 클릭하며 상세/메뉴 수집...")
    # 가상 렌더링 때문에 "한 번에 다"가 아니라
    # 스크롤 위치/DOM 렌더링이 바뀌면 다시 렌더링된 것들을 계속 처리해야 함.
    for round_idx in range(1, MAX_PROCESS_ROUNDS_PER_PAGE + 1):
        newly = process_visible_restaurants_once(page, search_frame, page_num, processed)
        total_processed += newly
        print(f"[PAGE {page_num}] round {round_idx}: 신규 처리 {newly}개 / 누적 {total_processed}개")

        # 신규 처리 0개면:
        # - 아직 아래쪽 식당이 DOM에 안 떠서 그럴 수 있으니 조금 더 아래로 스크롤하고 재시도
        if newly == 0:
            try:
                search_frame.mouse.wheel(0, 1600)
            except Exception:
                pass
            page.wait_for_timeout(500)

            # 그래도 0이면 종료(이 페이지에서 더 처리할 게 거의 없음)
            # (보수적으로 2번 연속 0이면 종료)
            newly2 = process_visible_restaurants_once(page, search_frame, page_num, processed)
            total_processed += newly2
            print(f"[PAGE {page_num}] extra try: 신규 처리 {newly2}개 / 누적 {total_processed}개")
            if newly2 == 0:
                break

    return total_processed


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = browser.new_context(locale="ko-KR", viewport={"width": 1500, "height": 950})
        page = context.new_page()

        page.goto(START_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(2200)

        search_frame = wait_for_search_iframe(page)
        total_pages = get_total_pages(search_frame, fallback=5)
        print(f"[INFO] 감지된 총 페이지 수: {total_pages}")

        grand_total = 0

        for page_num in range(1, total_pages + 1):
            if page_num != 1:
                # 페이지네이션 클릭 전에 위쪽으로 올려 버튼 보이게
                try:
                    search_frame.mouse.wheel(0, -6000)
                    page.wait_for_timeout(400)
                except Exception:
                    pass

                ok = go_to_page(search_frame, page_num)
                if not ok:
                    print(f"[WARN] {page_num}페이지 이동 실패 -> 스킵")
                    continue

            # 페이지별 완결 처리
            processed_cnt = process_one_page_fully(page, search_frame, page_num)
            grand_total += processed_cnt
            print(f"[PAGE {page_num}] 완료: 처리 {processed_cnt}개 / 전체 누적 {grand_total}개")

        print("\n[DONE] 전체 완료")
        print(f"CSV 저장 경로: {OUT_CSV.resolve()}")

        context.close()
        browser.close()


if __name__ == "__main__":
    main()