import csv
import os

def remove_duplicates():
    # 원본 파일 읽기
    exercises = set()  # 중복 제거를 위한 set
    with open("exercise_list.csv", mode="r", encoding="utf-8") as file:
        reader = csv.reader(file)
        header = next(reader)  # 헤더 저장
        for row in reader:
            if len(row) >= 2:
                exercises.add((row[0], row[1]))  # (이름, URL) 튜플로 저장
    
    # 중복 제거된 데이터를 새 파일에 저장
    with open("exercise_list_unique.csv", mode="w", encoding="utf-8", newline='') as file:
        writer = csv.writer(file)
        writer.writerow(header)  # 헤더 쓰기
        for exercise in sorted(exercises):  # 정렬된 순서로 저장
            writer.writerow(exercise)
    
    print(f"✅ 중복 제거 완료!")
    print(f"📊 원본 항목 수: {len(exercises)}")
    print(f"💾 저장된 파일: exercise_list_unique.csv")

if __name__ == "__main__":
    remove_duplicates() 