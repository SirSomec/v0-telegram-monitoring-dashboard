-- Включение/выключение мониторинга для подписки пользователя на канал.
-- Выполнить один раз на существующей БД: psql -f add_subscription_enabled.sql ... или аналог для вашей СУБД.

ALTER TABLE user_chat_subscriptions
ADD COLUMN IF NOT EXISTS enabled BOOLEAN NOT NULL DEFAULT true;
