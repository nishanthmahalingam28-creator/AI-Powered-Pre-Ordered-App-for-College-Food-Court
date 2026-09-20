-- ====================================================================
-- Migration: 001_student_dashboard_tables.sql
-- Purpose: Support student morning survey & personalized recommendations
-- Database: MySQL 8 (Aiven Cloud Production Compatible)
-- Safety: Non-destructive, idempotent (CREATE TABLE IF NOT EXISTS)
-- ====================================================================

-- 1. Student Morning Survey Table
CREATE TABLE IF NOT EXISTS morning_surveys (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    survey_date DATE NOT NULL,
    meal_preference VARCHAR(100) NOT NULL,
    hunger_level VARCHAR(50) NOT NULL,
    dietary_preference VARCHAR(50) NOT NULL DEFAULT 'any',
    meal_type VARCHAR(50) NOT NULL DEFAULT 'breakfast',
    mood_energy VARCHAR(50) NULL,
    food_restrictions VARCHAR(255) NULL,
    notes TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_morning_survey_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE,
    UNIQUE KEY uq_user_survey_date (user_id, survey_date),
    INDEX idx_survey_user (user_id),
    INDEX idx_survey_date (survey_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
