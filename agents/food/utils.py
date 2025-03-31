from typing import Dict, Any, Optional, List
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
import time
import json
import requests

# Docker에서 실행 중인 Qdrant 클라이언트 초기화 
qdrant_client = QdrantClient(
    url="http://localhost:6333",
    port=6333
)

# Qdrant 클라이언트 초기화
client = QdrantClient(host="localhost", port=6333)
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

def search_naver_food(query: str) -> List[Dict]:
    """
    네이버 검색을 통해 식품 정보 크롤링
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 헤드리스 모드
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        # 네이버 검색 URL
        url = f"https://search.naver.com/search.naver?where=nexearch&sm=top_hty&fbm=0&ie=utf8&query={query}+영양성분"
        driver.get(url)
        time.sleep(2)  # 페이지 로딩 대기
        
        # 검색 결과에서 영양 정보 추출
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        nutrition_info = []
        
        # 영양 정보가 있는 요소 찾기
        nutrition_elements = soup.find_all('div', class_='nutrition_info')
        for element in nutrition_elements:
            info = {
                'name': query,
                'nutrition': element.text.strip()
            }
            nutrition_info.append(info)
        
        return nutrition_info
    finally:
        driver.quit()

def get_food_info(query: str) -> List[Dict]:
    """
    여러 소스에서 식품 정보를 검색하고 통합
    """
    # 1. Qdrant에서 검색
    try:
        # 문장 임베딩 모델 초기화
        model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
        query_embedding = model.encode(query)
        
        # 음식명으로 검색
        name_results = qdrant_client.search(
            collection_name="food_names",
            query_vector=query_embedding.tolist(),
            limit=5
        )
        
        if name_results and len(name_results) > 0:
            return [{
                "name": result.payload.get("name"),
                "macro_text": result.payload.get("macro_text"),
                "nutrition_text": result.payload.get("nutrition_text")
            } for result in name_results]
            
    except Exception as e:
        print(f"Qdrant 검색 실패: {e}")
    
    # 2. 네이버 검색 결과
    naver_results = search_naver_food(query)
    if naver_results:
        return naver_results
    
    return []

def search_vector_db(query: str) -> Optional[Dict[str, Any]]:
    """벡터 DB에서 식품 정보 검색"""
    try:
        # 쿼리 임베딩
        query_vector = model.encode(query).tolist()
        
        # Qdrant 검색
        results = client.search(
            collection_name="food_macros",
            query_vector=query_vector,
            limit=1
        )
        print(results)
        if results:
            return {
                **results[0].payload,
                "confidence": results[0].score
            }
        return None
    except Exception as e:
        print(f"벡터 DB 검색 중 오류 발생: {e}")
        return None

def search_web_info(query: str) -> Optional[Dict[str, Any]]:
    """웹에서 식품 영양 정보 검색"""
    try:
        # 네이버 검색 API 사용 (예시)
        url = f"https://openapi.naver.com/v1/search/blog?query={query}+영양성분"
        headers = {
            "X-Naver-Client-Id": "YOUR_CLIENT_ID",
            "X-Naver-Client-Secret": "YOUR_CLIENT_SECRET"
        }
        response = requests.get(url, headers=headers)
        data = response.json()
        
        # 결과 파싱 및 반환
        if data.get("items"):
            return {
                "title": data["items"][0]["title"],
                "description": data["items"][0]["description"],
                "confidence": 0.7  # 웹 검색 결과는 신뢰도를 낮게 설정
            }
        return None
    except Exception as e:
        print(f"웹 검색 중 오류 발생: {e}")
        return None

def calculate_bmi(weight: float, height: float) -> float:
    """BMI 계산 (체중kg / 신장m^2)"""
    height_m = height / 100  # cm를 m로 변환
    return weight / (height_m * height_m)

def calculate_bmr(weight: float, height: float, age: int, gender: str) -> float:
    """기초대사량(BMR) 계산"""
    if gender == "남성":
        return 66.47 + (13.75 * weight) + (5.003 * height) - (6.755 * age)
    else:
        return 655.1 + (9.563 * weight) + (1.85 * height) - (4.676 * age)

def calculate_tdee(bmr: float, activity_level: str) -> float:
    """일일 총 에너지 소비량(TDEE) 계산"""
    activity_multipliers = {
        "거의 없음": 1.2,
        "가벼운": 1.375,
        "보통": 1.55,
        "활동적": 1.725,
        "매우 활동적": 1.9
    }
    return bmr * activity_multipliers.get(activity_level, 1.2)

def analyze_food_nutrition(food_name: str) -> Optional[Dict[str, Any]]:
    """식품의 영양소 분석"""
    try:
        # 벡터 DB에서 검색
        result = search_vector_db(food_name)
        if result and result.get("confidence", 0) > 0.8:
            return result
        
        # 벡터 DB에서 찾지 못한 경우 웹 검색
        web_result = search_web_info(food_name)
        if web_result:
            return web_result
        
        return None
    except Exception as e:
        print(f"영양소 분석 중 오류 발생: {e}")
        return None

  