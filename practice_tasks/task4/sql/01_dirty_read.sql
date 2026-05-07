-- =============================================================================
-- 1) DIRTY READ (грязное чтение)
-- =============================================================================
-- Условие: MySQL, уровень READ UNCOMMITTED для сессии B.
-- Две параллельные клиентские сессии (два окна mysql CLI или два GUI-таба).

-- Сессия A — шаги по порядку:
START TRANSACTION;
UPDATE accounts SET balance = 999 WHERE id = 1;
-- НЕ делайте COMMIT, пока в сессии B не выполнен SELECT ниже.

-- Сессия B — выполнить, пока A в открытой транзакции после UPDATE:
SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;
START TRANSACTION;
SELECT balance FROM accounts WHERE id = 1;
-- Ожидаемый результат: 999 (прочитано незафиксированное значение из A).

-- Сессия A — откат:
ROLLBACK;

-- Сессия B — повторное чтение после ROLLBACK в A:
SELECT balance FROM accounts WHERE id = 1;
COMMIT;

-- Как избежать: не использовать READ UNCOMMITTED; для InnoDB использовать
-- как минимум READ COMMITTED (по умолчанию REPEATABLE READ), не читать
-- незафиксированные данные чужих транзакций.
