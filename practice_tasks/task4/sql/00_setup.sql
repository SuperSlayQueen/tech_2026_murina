-- База: isolation_lab (см. docker-compose.yml)
-- Кодировка utf8mb4

CREATE TABLE IF NOT EXISTS accounts (
  id INT PRIMARY KEY,
  balance INT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
  id INT AUTO_INCREMENT PRIMARY KEY,
  amount INT NOT NULL
);

INSERT INTO accounts (id, balance) VALUES (1, 100)
  ON DUPLICATE KEY UPDATE balance = 100;

DELETE FROM orders;
INSERT INTO orders (amount) VALUES (10), (20), (30);
