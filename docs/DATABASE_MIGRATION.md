# Production Database Migration Strategy

**Project**: AI-Powered Pre-Ordered App for College Food Court  
**Engine**: MySQL 8.0 (InnoDB)  
**Database**: `food_court_db`  
**Character Set**: `utf8mb4`  
**Collation**: `utf8mb4_unicode_ci`  

---

## 1. Principles of Production Schema Migration
1. **Never Destroy Data**: Destructive operations (`DROP TABLE`, `TRUNCATE`, `DROP COLUMN`) are strictly forbidden in production.
2. **Backward Compatibility First**: When introducing new columns or indexes, ensure old code versions can function while the new version deploys.
3. **Transactional DDL & Online DDL**: For large tables (`orders`, `notifications`), use MySQL Online DDL (`ALGORITHM=INPLACE, LOCK=NONE`) to prevent table locking during index creation.
4. **Idempotency**: All migration scripts must use `IF NOT EXISTS` or check `information_schema` before execution.

---

## 2. Table Inventory & Verification Checklist

| Table Name | Phase Introduced | Key Indexes | Foreign Key Cascades |
| :--- | :--- | :--- | :--- |
| `users` | Phase 1 & 2 | `idx_user_role`, `idx_user_email` | Primary entity |
| `customer_profiles` | Phase 2 | `idx_customer_type`, `idx_customer_mobile` | `ON DELETE CASCADE` from `users` |
| `shops` | Phase 3 & 6 | `slug` (UNIQUE) | `ON DELETE SET NULL` from `users` |
| `menu_items` | Phase 3 & 6 | `idx_menu_shop`, `idx_menu_category` | `ON DELETE CASCADE` from `shops` |
| `orders` | Phase 4 & 5 | `order_reference`, `idx_order_status`, `idx_order_customer`, `idx_order_shop` | `ON DELETE CASCADE` from `users`, `shops` |
| `order_items` | Phase 4 | `fk_item_order`, `fk_item_menu` | `ON DELETE CASCADE` from `orders` |
| `payments` | Phase 5 | `idx_payment_gateway_order`, `idx_payment_gateway_payment`, `idx_payment_status` | `ON DELETE CASCADE` from `orders` |
| `otp_codes` | Phase 2 & 9 | `idx_otp_target`, `idx_otp_verify_check` | Independent audit store |
| `audit_logs` | Phase 6 | `idx_audit_actor`, `idx_audit_entity`, `idx_audit_created` | `ON DELETE CASCADE` from `users` |
| `notifications` | Phase 7 | `idx_notification_user_unread`, `idx_notification_user_created`, `idx_notification_order` | `ON DELETE CASCADE` from `users`, `orders` |

---

## 3. Step-by-Step Initial Production Setup

```bash
# 1. Connect to MySQL administrative console
mysql -u root -p

# 2. Execute authoritative production schema
mysql -u root -p food_court_db < /var/www/foodcourt/database/schema.sql

# 3. Seed baseline administrative and stall accounts
mysql -u root -p food_court_db < /var/www/foodcourt/database/seed.sql

# 4. Verify all 10 core tables exist
mysql -u root -p food_court_db -e "SHOW TABLES;"
```

---

## 4. Zero-Downtime Migration Execution Runbook

When applying incremental schema migrations in future updates:

```bash
# Step A: Take pre-migration snapshot
mysqldump -u root -p --single-transaction --routines --triggers food_court_db > pre_migration_$(date +%Y%m%d_%H%M%S).sql

# Step B: Apply non-blocking migration script
mysql -u root -p food_court_db < /var/www/foodcourt/database/migrations/001_phase9_hardening.sql

# Step C: Verify schema integrity
mysql -u root -p food_court_db -e "CHECK TABLE users, customer_profiles, shops, menu_items, orders, order_items, payments, notifications;"

# Step D: Test application readiness probe
curl -f http://127.0.0.1:5000/api/ready
```
