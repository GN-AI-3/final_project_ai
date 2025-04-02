-- 기존 테이블 삭제
DROP TABLE IF EXISTS reservations;
DROP TABLE IF EXISTS users;

-- users 테이블 생성
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('trainer', 'client'))
);

-- reservations 테이블 생성
CREATE TABLE reservations (
    reservation_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id),
    trainer_id INTEGER REFERENCES users(user_id),
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 샘플 데이터 삽입
-- 트레이너 데이터
INSERT INTO users (name, role) VALUES
('박지훈', 'trainer'),
('김민수', 'trainer'),
('이영희', 'trainer');

-- 클라이언트 데이터
INSERT INTO users (name, role) VALUES
('김철수', 'client'),
('이영수', 'client'),
('박지성', 'client');

-- 예약 데이터
INSERT INTO reservations (user_id, trainer_id, start_time, end_time) VALUES
(4, 1, '2025-04-01 09:00:00', '2025-04-01 10:00:00'),
(4, 1, '2025-04-08 15:00:00', '2025-04-08 16:00:00'),
(5, 2, '2025-04-02 14:00:00', '2025-04-02 15:00:00'),
(6, 3, '2025-04-03 11:00:00', '2025-04-03 12:00:00'); 