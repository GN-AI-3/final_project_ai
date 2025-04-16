import time
import json
import csv
import os
import random
from selenium import webdriver
from selenium_stealth import stealth
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

def log_progress(message):
    print(f"📝 {message}")

def setup_driver():
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--disable-web-security")
    options.add_argument("--disable-features=IsolateOrigins,site-per-process")
    
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
    ]
    options.add_argument(f"user-agent={random.choice(user_agents)}")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    stealth(driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
            )
    
    return driver

def extract_media_elements(article):
    media_data = {}
    
    # Classification 섹션 이전의 이미지와 비디오만 찾기
    classification_section = article.find('h2', string='Classification')
    if classification_section:
        # Classification 이전의 모든 요소 찾기
        previous_elements = classification_section.find_previous_siblings()
        
        # 이미지 찾기
        images = []
        for element in previous_elements:
            if element.name == 'img':
                images.append({'src': element.get('src', ''), 'alt': element.get('alt', '')})
        if images:
            media_data['images'] = images
        
        # 비디오 찾기
        videos = []
        for element in previous_elements:
            if element.name == 'video':
                videos.append({'src': element.get('src', ''), 'poster': element.get('poster', '')})
        if videos:
            media_data['videos'] = videos
    
    return media_data

def normalize_text(text):
    """텍스트에서 불필요한 공백을 제거하고 정규화합니다."""
    if not text:
        return text
    # 모든 종류의 공백을 단일 공백으로 정규화
    return ' '.join(text.split())

def extract_classification_table(section):
    content = {}
    
    # Classification 섹션의 표 찾기
    table = section.find_next('table')
    if table:
        # 표의 모든 행 처리
        rows = table.find_all('tr')
        for row in rows:
            # 행의 모든 셀 처리
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 2:
                key = normalize_text(cells[0].get_text())
                value = normalize_text(cells[1].get_text())
                if key and value:
                    content[key] = value
    
    return content

def extract_section_content(section):
    content = {}
    
    # 현재 섹션의 다음 요소부터 다음 h2 태그 전까지의 모든 요소 처리
    current = section.find_next()
    while current:
        # article 태그를 벗어나면 중단
        if not current.find_parent('article'):
            break
            
        # 다음 h2 태그를 만나면 중단
        if current.name == 'h2':
            break
            
        if current.name == 'p':
            # strong 태그가 있는 경우
            strong = current.find('strong')
            if strong:
                key = normalize_text(strong.get_text())
                # strong 태그 이후의 텍스트를 값으로 사용
                value = strong.next_sibling
                if value:
                    value = normalize_text(value.get_text())
                if key and value:
                    content[key] = value
            else:
                # strong 태그가 없는 경우
                text = normalize_text(current.get_text())
                if text:
                    # 이전 요소가 strong 태그가 있는 p 태그인지 확인
                    prev_p = current.find_previous('p')
                    if prev_p and prev_p.find('strong'):
                        # 이전 p 태그의 strong 태그가 키가 됨
                        key = normalize_text(prev_p.find('strong').get_text())
                        if key in content:
                            if isinstance(content[key], str):
                                content[key] = [content[key]]
                            content[key].append(text)
                        else:
                            content[key] = text
                    else:
                        # 이전에 strong 태그가 있는 p 태그가 없다면
                        # 섹션 이름(h2 태그)이 키가 됨
                        section_name = normalize_text(section.get_text())
                        if section_name in content:
                            if isinstance(content[section_name], str):
                                content[section_name] = [content[section_name]]
                            content[section_name].append(text)
                        else:
                            content[section_name] = text
        elif current.name == 'ul':
            # ul 태그의 모든 li 태그를 처리
            li_items = []
            processed_items = set()  # 중복 방지를 위한 집합
            
            for li in current.find_all('li', recursive=False):  # 최상위 li만 처리
                li_text = normalize_text(li.get_text())
                if li_text:
                    # 중첩된 ul이 있는지 확인
                    nested_ul = li.find('ul')
                    if nested_ul:
                        # 중첩된 ul이 있는 경우, 상위 li의 텍스트를 키로 사용하고 중첩된 li들의 텍스트를 값으로 사용
                        nested_items = [normalize_text(nested_li.get_text()) for nested_li in nested_ul.find_all('li')]
                        if nested_items:
                            # 상위 li의 텍스트에서 중첩된 항목들의 텍스트를 제거
                            parent_text = li_text
                            for nested_item in nested_items:
                                if nested_item in parent_text:
                                    parent_text = parent_text.replace(nested_item, '').strip()
                            if parent_text:
                                # 중첩된 항목들을 처리된 항목 집합에 추가
                                for item in nested_items:
                                    processed_items.add(item)
                                li_items.append({parent_text: nested_items})
                    else:
                        # 중첩된 ul이 없는 경우, 중복되지 않은 항목만 추가
                        if li_text not in processed_items:
                            processed_items.add(li_text)
                            li_items.append(li_text)
            
            if li_items:
                # ul 태그의 이전 p 태그 중 가장 가까운 strong 태그를 가진 p 태그 찾기
                prev_p = current.find_previous('p')
                while prev_p and not prev_p.find('strong'):
                    prev_p = prev_p.find_previous('p')
                
                if prev_p and prev_p.find('strong'):
                    # 이전 p 태그의 strong 태그가 키가 됨
                    key = normalize_text(prev_p.find('strong').get_text())
                    if key in content:
                        if isinstance(content[key], str):
                            content[key] = [content[key]]
                        # 중복되지 않은 항목만 추가
                        for item in li_items:
                            if isinstance(item, dict):
                                # 딕셔너리인 경우 (중첩된 항목)
                                content[key].append(item)
                            elif item not in processed_items:
                                # 문자열인 경우 (일반 항목)
                                content[key].append(item)
                    else:
                        content[key] = li_items
                else:
                    # 이전에 strong 태그가 있는 p 태그가 없다면
                    # 섹션 이름(h2 태그)이 키가 됨
                    section_name = normalize_text(section.get_text())
                    if section_name in content:
                        if isinstance(content[section_name], str):
                            content[section_name] = [content[section_name]]
                        # 중복되지 않은 항목만 추가
                        for item in li_items:
                            if isinstance(item, dict):
                                # 딕셔너리인 경우 (중첩된 항목)
                                content[section_name].append(item)
                            elif item not in processed_items:
                                # 문자열인 경우 (일반 항목)
                                content[section_name].append(item)
                    else:
                        content[section_name] = li_items
        
        # 다음 요소 찾기 (연속된 p와 li 태그를 모두 처리하기 위해)
        next_element = current.find_next()
        if next_element and next_element.name in ['p', 'li']:
            current = next_element
        else:
            current = next_element
    
    return content

def get_structured_data(driver, url, name):
    driver.get(url)
    time.sleep(random.uniform(3, 7))  # 랜덤 대기
    
    log_progress(f"🔍 {name} 정보 추출 중...")
    wait = WebDriverWait(driver, 15)
    wait.until(lambda driver: driver.execute_script("return document.readyState") == "complete")
    
    exercise_data = {
        "exercise_name": name,
        "url": url
    }
    
    try:
        # BeautifulSoup으로 HTML 파싱
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        title_tag = soup.find('h1', class_='page-title')
        if title_tag:
            exercise_data['exercise_name'] = title_tag.get_text(strip=True)
        else:
            exercise_data['exercise_name'] = name
        
        # 첫 번째 article 태그 찾기
        article = soup.find('article')
        if not article:
            raise Exception("article 태그를 찾을 수 없습니다.")
        
        # 미디어 요소 추출 (Classification 이전의 요소만)
        media_data = extract_media_elements(article)
        if media_data:
            exercise_data['media'] = media_data
        
        # Classification부터 시작하는 모든 h2 섹션 처리
        start_section = article.find('h2', string='Classification')
        if start_section:
            current = start_section
            while current:
                # article 태그를 벗어나면 중단
                if not current.find_parent('article'):
                    break
                    
                if current.name == 'h2':
                    section_name = current.get_text(strip=True)
                    
                    # Classification 섹션인 경우 표 형식으로 처리
                    if section_name == 'Classification':
                        section_content = extract_classification_table(current)
                    else:
                        # 다른 섹션들은 p/strong 태그 구조로 처리
                        section_content = extract_section_content(current)
                    
                    if section_content:
                        exercise_data[section_name] = section_content
                
                current = current.find_next()
        
        log_progress(f"✅ {name} 정보 추출 완료!")
        
    except Exception as e:
        log_progress(f"🚨 {name} 정보 추출 실패: {str(e)}")
    
    return exercise_data

def save_progress(exercise_data):
    # 프로젝트 루트 디렉토리 경로 설정 (data/src -> data -> project root)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    json_dir = os.path.join(project_root, "data", "exercise_list_json_title")
    
    # JSON 디렉토리가 없으면 생성
    os.makedirs(json_dir, exist_ok=True)
    
    base_name = exercise_data['exercise_name'].replace(' ', '_')
    file_name = os.path.join(json_dir, f"{base_name}.json")
    counter = 1
    
    # 파일이 이미 존재하는 경우 숫자를 붙여서 시도
    while os.path.exists(file_name):
        file_name = os.path.join(json_dir, f"{base_name}_{counter}.json")
        counter += 1
    
    try:
        with open(file_name, mode='w', encoding='utf-8') as file:
            json.dump(exercise_data, file, ensure_ascii=False, indent=4)
        log_progress(f"💾 저장 완료: {file_name}")
    except Exception as e:
        log_progress(f"🚨 저장 오류: {str(e)}")

def main():
    driver = setup_driver()
    failed_exercises = []  # 실패한 운동 이름을 저장할 리스트
    
    try:
        # 프로젝트 루트 디렉토리 경로 설정 (data/src -> data -> project root)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        csv_file = os.path.join(project_root, "data", "exercise_list_csv", "exercise_list_unique.csv")
        
        with open(csv_file, mode="r", encoding="utf-8") as file:
            reader = csv.reader(file)
            next(reader)  # 헤더 스킵
            for row in reader:
                if len(row) < 2:
                    continue
                name, url = row
                try:
                    page_data = get_structured_data(driver, url, name)
                    save_progress(page_data)
                except Exception as e:
                    log_progress(f"🚨 {name} 처리 중 오류 발생: {str(e)}")
                    failed_exercises.append(name)
    except Exception as e:
        log_progress(f"🚨 전체 오류 발생: {str(e)}")
    finally:
        driver.quit()
        
        # 실패한 운동 목록 출력
        if failed_exercises:
            log_progress("\n📊 실패한 운동 목록:")
            for exercise in failed_exercises:
                log_progress(f"- {exercise}")
            log_progress(f"\n총 {len(failed_exercises)}개의 운동이 실패했습니다.")
        else:
            log_progress("\n✨ 모든 운동이 성공적으로 처리되었습니다!")

if __name__ == "__main__":
    main() 