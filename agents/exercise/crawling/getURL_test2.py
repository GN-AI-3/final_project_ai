import time
from selenium import webdriver
from selenium_stealth import stealth
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import random
import csv

# 중간 저장 함수 (CSV 파일로 저장)
def save_progress(exercise_data):
    try:
        with open('filtered_exercise_links.csv', mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            for data in exercise_data:
                writer.writerow(data)
        print("🔄 중간 결과 저장 완료.")
    except Exception as e:
        print(f"🚨 중간 저장 오류: {str(e)}")

# 진행 상황 로그 출력
def log_progress(message):
    print(f"📝 {message}")

def setup_driver():
    options = Options()
    
    # 기본 설정
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    
    # 봇 감지 우회 설정
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--disable-web-security")
    options.add_argument("--disable-features=IsolateOrigins,site-per-process")
    
    # 랜덤한 User-Agent 설정
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
    ]
    options.add_argument(f"user-agent={random.choice(user_agents)}")
    
    # WebDriver 실행
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    # Stealth 모드 설정
    stealth(driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
            )
    
    return driver

def get_exercise_links_from_page(driver, url):
    # 페이지 접속
    driver.get(url)
    
    # 랜덤한 대기 시간 (3-7초)
    wait_time = random.uniform(3, 7)
    log_progress(f"⏳ {wait_time:.1f}초 대기 중...")
    time.sleep(wait_time)
    
    # 페이지 로딩 확인
    log_progress("🔍 페이지 로딩 확인 중...")
    wait = WebDriverWait(driver, 15)  # 타임아웃 15초로 증가
    
    # 페이지가 완전히 로드될 때까지 대기
    wait.until(lambda driver: driver.execute_script("return document.readyState") == "complete")
    
    # 운동 링크 추출
    exercise_links = []
    try:
        # 운동 관련 링크 찾기
        exercise_links = wait.until(
            EC.presence_of_all_elements_located((By.XPATH, "//a[contains(@href, '/WeightExercises/')]"))
        )
        log_progress(f"✅ 운동 링크 {len(exercise_links)}개 찾음.")
    except:
        log_progress("🚨 운동 링크 찾지 못함.")
    
    return exercise_links

def main():
    try:
        log_progress("🚀 크롬 드라이버 설정 중...")
        driver = setup_driver()
        log_progress("✅ 크롬 드라이버 설정 완료!")
        
        # CSV에서 기존 링크들 불러오기
        log_progress("🌐 CSV에서 링크들 불러오는 중...")
        with open('exercise_links.csv', mode='r', encoding='utf-8') as file:
            reader = csv.reader(file)
            csv_links = [row[1] for row in reader if row]  # 두 번째 열에 있는 링크만 추출

        log_progress(f"✅ 총 {len(csv_links)}개의 링크가 CSV에 저장됨.")
        
        # 운동 링크들을 저장할 리스트
        exercise_data = []
        
        # 각 링크에서 운동 관련 링크 추출
        for idx, link in enumerate(csv_links, 1):
            log_progress(f"🚀 {idx}/{len(csv_links)} 번째 링크 처리 중: {link}")
            try:
                exercise_links = get_exercise_links_from_page(driver, link)
                for exercise in exercise_links:
                    name = exercise.text.strip()
                    href = exercise.get_attribute('href')
                    if name and href:
                        exercise_data.append([name, href])
            except Exception as e:
                log_progress(f"🚨 오류 발생: {str(e)}")
                continue

            # 중간 저장
            if idx % 10 == 0:
                save_progress(exercise_data)
                exercise_data = []  # 저장 후 리스트 초기화
        
        # 최종 저장
        save_progress(exercise_data)
        
    except Exception as e:
        log_progress(f"🚨 오류 발생: {str(e)}")
        log_progress("상세 오류 정보:")
        print(e.__class__.__name__)
        
    finally:
        input("Press Enter to exit...")
        driver.quit()

if __name__ == "__main__":
    main()
