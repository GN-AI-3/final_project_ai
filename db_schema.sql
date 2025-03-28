-- 헬스장 출석률 알림 시스템을 위한 데이터베이스 스키마

-- 기존 테이블 삭제 (필요한 경우)
DROP TABLE IF EXISTS attendance_records;
DROP TABLE IF EXISTS users;

-- 사용자 테이블
CREATE TABLE users (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(50),
    fcm_token VARCHAR(255),
    attendance_rate INTEGER DEFAULT 0,
    personal_goal VARCHAR(255) DEFAULT '일반',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 출석 기록 테이블
CREATE TABLE attendance_records (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES users(id),
    check_in TIMESTAMP NOT NULL,
    check_out TIMESTAMP,
    duration_minutes INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스 생성
CREATE INDEX idx_attendance_user_id ON attendance_records(user_id);
CREATE INDEX idx_attendance_check_in ON attendance_records(check_in);

-- 샘플 데이터 삽입
INSERT INTO users (id, name, email, phone, attendance_rate, personal_goal) VALUES
('user1', '김건강', 'kim@example.com', '010-1234-5678', 85, '체중 감량'),
('user2', '이근육', 'lee@example.com', '010-2345-6789', 65, '근력 향상'),
('user3', '박활력', 'park@example.com', '010-3456-7890', 45, '체력 증진'),
('user4', '최슬림', 'choi@example.com', '010-4567-8901', 90, '체형 관리'),
('user5', '정건강', 'jung@example.com', '010-5678-9012', 30, '정신적 건강 관리'),
('user6', '강단련', 'kang@example.com', '010-6789-0123', 75, '전체적인 건강 관리');

-- 현재 날짜를 기준으로 샘플 출석 기록 생성
INSERT INTO attendance_records (user_id, check_in, check_out, duration_minutes) VALUES
('user1', CURRENT_DATE - INTERVAL '1 day' + TIME '10:00:00', CURRENT_DATE - INTERVAL '1 day' + TIME '11:30:00', 90),
('user1', CURRENT_DATE - INTERVAL '3 day' + TIME '09:00:00', CURRENT_DATE - INTERVAL '3 day' + TIME '10:45:00', 105),
('user1', CURRENT_DATE - INTERVAL '5 day' + TIME '17:00:00', CURRENT_DATE - INTERVAL '5 day' + TIME '18:30:00', 90),
('user2', CURRENT_DATE - INTERVAL '2 day' + TIME '11:00:00', CURRENT_DATE - INTERVAL '2 day' + TIME '12:30:00', 90),
('user2', CURRENT_DATE - INTERVAL '4 day' + TIME '18:00:00', CURRENT_DATE - INTERVAL '4 day' + TIME '19:45:00', 105),
('user3', CURRENT_DATE - INTERVAL '1 day' + TIME '15:00:00', CURRENT_DATE - INTERVAL '1 day' + TIME '16:00:00', 60),
('user4', CURRENT_DATE - INTERVAL '1 day' + TIME '08:00:00', CURRENT_DATE - INTERVAL '1 day' + TIME '09:30:00', 90),
('user4', CURRENT_DATE - INTERVAL '2 day' + TIME '08:00:00', CURRENT_DATE - INTERVAL '2 day' + TIME '09:45:00', 105),
('user4', CURRENT_DATE - INTERVAL '3 day' + TIME '08:00:00', CURRENT_DATE - INTERVAL '3 day' + TIME '09:30:00', 90),
('user4', CURRENT_DATE - INTERVAL '5 day' + TIME '08:00:00', CURRENT_DATE - INTERVAL '5 day' + TIME '09:15:00', 75),
('user5', CURRENT_DATE - INTERVAL '7 day' + TIME '19:00:00', CURRENT_DATE - INTERVAL '7 day' + TIME '20:00:00', 60),
('user6', CURRENT_DATE - INTERVAL '1 day' + TIME '14:00:00', CURRENT_DATE - INTERVAL '1 day' + TIME '15:30:00', 90),
('user6', CURRENT_DATE - INTERVAL '3 day' + TIME '14:00:00', CURRENT_DATE - INTERVAL '3 day' + TIME '15:30:00', 90);

-- 뷰 생성: 사용자별 출석률 계산 (지난 30일 기준)
CREATE OR REPLACE VIEW user_attendance_stats AS
SELECT 
    u.id,
    u.name,
    u.personal_goal,
    COUNT(a.id) AS total_visits_30_days,
    GREATEST(0, LEAST(100, (COUNT(a.id) * 100 / 30))) AS attendance_rate_30_days
FROM 
    users u
LEFT JOIN 
    attendance_records a ON u.id = a.user_id AND a.check_in >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY 
    u.id, u.name, u.personal_goal;

-- 비고: 실제 환경에서는 이 스크립트를 데이터베이스에 직접 적용해야 합니다.
-- PostgreSQL 명령어: psql -U postgres -d gym_attendance -f db_schema.sql 