-- =============================================================================
-- 3) PHANTOM READ (фантомное чтение)
-- =============================================================================
-- На READ COMMITTED второй диапазонный SELECT в транзакции A видит новую строку,
-- вставленную и зафиксированную в B.

-- Сессия A:
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
START TRANSACTION;
SELECT id, amount FROM orders WHERE amount > 15;
-- Запомните число строк.

-- Сессия B:
START TRANSACTION;
INSERT INTO orders (amount) VALUES (99);
COMMIT;

-- Сессия A — повтор того же условия:
SELECT id, amount FROM orders WHERE amount > 15;
-- Ожидаемый результат: на одну строку больше (появился «фантом»).

COMMIT;

-- Очистка вставленной строки (по необходимости):
DELETE FROM orders WHERE amount = 99;

-- Как избежать: SERIALIZABLE или блокировки диапазона (в InnoDB при RR часть
-- фантомов блокируется next-key locks; для демонстрации фантома удобен RC).
