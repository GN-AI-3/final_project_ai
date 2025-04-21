import pdfplumber
import re
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.http import models
import json

def extract_text_and_table_from_pdf(file_path):
    text_data = []
    table_data = []
    
    with pdfplumber.open(file_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            # 페이지별 텍스트 추출
            text = page.extract_text()
            text_data.append((page_num, text))
            
            # 페이지별 표 추출
            tables = page.extract_tables()
            if tables:
                table_data.append((page_num, tables))
    
    return text_data, table_data

def process_text_to_chunks(text_data):
    chunks = []
    for page_num, text in text_data:
        if "비타민 A" in text:
            chunks.append({
                "영양소": "비타민 A",
                "권장섭취량": "900μg/일",
                "결핍증상": "야맹증, 면역력 저하",
                "연령대": "성인",
                "성별": "남성",
                "페이지": page_num
            })
        
        if "비타민 D" in text:
            chunks.append({
                "영양소": "비타민 D",
                "권장섭취량": "800 IU/일",
                "결핍증상": "뼈 약화, 면역력 저하",
                "연령대": "성인",
                "성별": "여성",
                "페이지": page_num
            })
    
    return chunks

def process_table_to_chunks(table_data):
    chunks = []
    for page_num, tables in table_data:
        for table in tables:
            for row in table:
                if len(row) >= 3:
                    nutrient = row[0]
                    recommended_intake = row[1]
                    deficiency = row[2]
                    chunks.append({
                        "영양소": nutrient,
                        "권장섭취량": recommended_intake,
                        "결핍증상": deficiency,
                        "페이지": page_num
                    })
    return chunks

def main():
    # PDF 파일 경로
    file_path = "1.+[비매품용]+2020+한국인+영양소+섭취기준+활용.pdf"
    
    # 1. PDF에서 텍스트와 표 추출
    print("PDF 파일에서 데이터 추출 중...")
    text_data, table_data = extract_text_and_table_from_pdf(file_path)
    print(f"추출된 텍스트 페이지 수: {len(text_data)}")
    print(f"추출된 표 페이지 수: {len(table_data)}")
    
    # 2. 텍스트와 표 데이터 처리
    print("데이터 처리 중...")
    text_chunks = process_text_to_chunks(text_data)
    table_chunks = process_table_to_chunks(table_data)
    all_chunks = text_chunks + table_chunks
    
    # 3. 임베딩 생성
    print("임베딩 생성 중...")
    model = SentenceTransformer('paraphrase-MiniLM-L6-v2')
    embeddings = model.encode([chunk['영양소'] + " " + chunk['권장섭취량'] for chunk in all_chunks])
    
    # 4. Qdrant에 저장
    print("Qdrant에 데이터 저장 중...")
    client = QdrantClient("localhost", port=6333)
    
    # 컬렉션 생성 (이미 존재하면 무시)
    client.recreate_collection(
        collection_name="nutrition_data",
        vectors_config=models.VectorParams(
            size=384,  # SentenceTransformer 모델의 임베딩 차원
            distance=models.Distance.COSINE
        )
    )
    
    # 데이터 포인트 생성 및 업로드
    points = []
    for i, (chunk, embedding) in enumerate(zip(all_chunks, embeddings)):
        points.append(models.PointStruct(
            id=i,
            vector=embedding.tolist(),
            payload=chunk
        ))
    
    # 배치로 업로드
    client.upsert(
        collection_name="nutrition_data",
        points=points
    )
    
    print("처리 완료!")

if __name__ == "__main__":
    main()