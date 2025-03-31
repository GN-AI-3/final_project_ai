import time
import json
import csv
import os
import random
from selenium import webdriver
from selenium_stealth import stealth
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

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

def get_all_info_from_page(driver, url, name):
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
        all_text = driver.find_element(By.TAG_NAME, 'body').text.strip()
        
        if "Classification" in all_text:
            classification_text = all_text.split("Utility: ")[1].split("Instructions")[0].strip()
            exercise_data["Classification"] = {
                "Utility": classification_text.split("Mechanics: ")[0].strip(),
                "Mechanics": classification_text.split("Mechanics: ")[1].split("Force")[0].strip(),
                "Force": classification_text.split("Force: ")[1].strip()
            }
        
        if "Instructions" in all_text:
            instructions_text = all_text.split("Preparation\n")[1].split("Comments")[0].strip()
            exercise_data["Instructions"] = {
                "Preparation": instructions_text.split("Execution")[0].strip(),
                "Execution": instructions_text.split("Execution")[1].strip()
            }
        
        if "Comments" in all_text:
            comments_text = all_text.split("Comments")[1].split("Muscles")[0].strip()
            if "Also see" in comments_text:
                exercise_data["Comments"] = comments_text.split("Also see")[0].strip()
            else:
                exercise_data["Comments"] = comments_text
        
        if "Muscles" in all_text:
            muscles_text = all_text.split("Comments")[1].split("Target")[1].strip()
            # Exercise Directory 이전의 텍스트만 추출
            muscles_text = muscles_text.split("Exercise Directory")[0].strip()
            
            exercise_data["Muscles"] = {}
            remaining_text = muscles_text
            
            # 1. Target (항상 존재)
            exercise_data["Muscles"]["Target"] = remaining_text.split("Synergists")[0].strip()
            
            # 2. Synergists (항상 존재)
            # 다음 섹션 찾기
            remaining_text = remaining_text.split("Synergists")[1]
            next_sections = ["Dynamic Stabilizers", "Stabilizers", "Antagonist Stabilizers"]
            next_section = None
            for section in next_sections:
                if section in remaining_text:
                    next_section = section
                    break
            
            if next_section:
                exercise_data["Muscles"]["Synergists"] = remaining_text.split(next_section)[0].strip()
            else:
                exercise_data["Muscles"]["Synergists"] = remaining_text.split("Exercise Directory")[0].strip()
                remaining_text = ""
            
            # 3. Dynamic Stabilizers (선택적)
            if "Dynamic Stabilizers" in remaining_text:
                remaining_text = remaining_text.split("Dynamic Stabilizers")[1]
                next_sections = ["Stabilizers", "Antagonist Stabilizers"]
                next_section = None
                for section in next_sections:
                    if section in remaining_text:
                        next_section = section
                        break
                
                if next_section:
                    exercise_data["Muscles"]["Dynamic Stabilizers"] = remaining_text.split(next_section)[0].strip().replace("\n", ", ")
                else:
                    exercise_data["Muscles"]["Dynamic Stabilizers"] = remaining_text.split("Exercise Directory")[0].strip().replace("\n", ", ")
                    remaining_text = ""
            
            # 4. Stabilizers (선택적)
            if "Stabilizers" in remaining_text:
                remaining_text = remaining_text.split("Stabilizers")[1]
                if "Antagonist Stabilizers" in remaining_text:
                    exercise_data["Muscles"]["Stabilizers"] = remaining_text.split("Antagonist Stabilizers")[0].strip().replace("\n", ", ")
                else:
                    exercise_data["Muscles"]["Stabilizers"] = remaining_text.split("Exercise Directory")[0].strip().replace("\n", ", ")
                    remaining_text = ""
            
            # 5. Antagonist Stabilizers (선택적)
            if "Antagonist Stabilizers" in remaining_text:
                remaining_text = remaining_text.split("Antagonist Stabilizers")[1]
                exercise_data["Muscles"]["Antagonist Stabilizers"] = remaining_text.split("Exercise Directory")[0].strip().replace("\n", ", ")
        
        log_progress(f"✅ {name} 정보 추출 완료!")
        
    except Exception as e:
        log_progress(f"🚨 {name} 정보 추출 실패: {str(e)}")
    
    return exercise_data

def save_progress(exercise_data):
    # 프로젝트 루트 디렉토리 경로 설정 (data/src -> data -> project root)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    json_dir = os.path.join(project_root, "data", "exercise_list_json")
    
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
    
    try:
        # 프로젝트 루트 디렉토리 경로 설정 (data/src -> data -> project root)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        csv_file = os.path.join(project_root, "data", "exercise_list_csv", "exercise_list_unique.csv")
        
        with open(csv_file, mode="r", encoding="utf-8") as file:
            reader = csv.reader(file)
            next(reader)  # 헤더 스킵
            for row in reader:
                if len(row) < 2:
                    continue
                name, url = row
                page_data = get_all_info_from_page(driver, url, name)
                save_progress(page_data)
    except Exception as e:
        log_progress(f"🚨 전체 오류 발생: {str(e)}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
