-- =============================================================================
-- 4) LOST UPDATE (потерянное обновление)
-- =============================================================================
-- Две транзакции читают одно и то же значение и оба пишут «вслепую» — одно
-- обновление теряется.

-- Подготовка:
UPDATE accounts SET balance = 100 WHERE id = 1;

-- Сессия A:
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
START TRANSACTION;
SELECT balance FROM accounts WHERE id = 1;  -- 100

-- Сессия B:
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
START TRANSACTION;
SELECT balance FROM accounts WHERE id = 1;  -- 100

-- Сессия A: «увеличить на 10» на основе прочитанного 100
UPDATE accounts SET balance = 100 + 10 WHERE id = 1;
COMMIT;

-- Сессия B: «увеличить на 20» на основе своего прочитанного 100 (устарело)
UPDATE accounts SET balance = 100 + 20 WHERE id = 1;
COMMIT;

-- Итог в таблице:
SELECT balance FROM accounts WHERE id = 1;
-- Ожидаемый результат: 120 (обновление +10 из A потеряно, осталось последнее
-- записанное значение B). Если бы порядок COMMIT был другой, могло бы остаться 110.

-- Восстановление:
UPDATE accounts SET balance = 100 WHERE id = 1;

-- Как избежать: SELECT ... FOR UPDATE при чтении, атомарное выражение
-- UPDATE accounts SET balance = balance + 10 WHERE id = 1, оптимистичные
-- версии (столбец version), или SERIALIZABLE.
