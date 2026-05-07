-- =============================================================================
-- 2) NON-REPEATABLE READ (неповторяемое чтение)
-- =============================================================================
-- Уровень READ COMMITTED: один и тот же SELECT в транзакции A видит разные строки
-- после COMMIT чужой транзакции B.

-- Сессия A:
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
START TRANSACTION;
SELECT balance FROM accounts WHERE id = 1;
-- Запомните значение (например 100).

-- Сессия B (параллельно):
START TRANSACTION;
UPDATE accounts SET balance = 200 WHERE id = 1;
COMMIT;

-- Сессия A — тот же запрос в той же транзакции:
SELECT balance FROM accounts WHERE id = 1;
-- Ожидаемый результат: 200 (отличается от первого чтения).

COMMIT;

-- Восстановление данных для следующих тестов:
UPDATE accounts SET balance = 100 WHERE id = 1;

-- Как избежать: уровень REPEATABLE READ / SERIALIZABLE, либо явные блокировки
-- (SELECT ... FOR UPDATE) на читаемых строках.
