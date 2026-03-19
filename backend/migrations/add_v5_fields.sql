-- ============================================================================
--  V5 考点分类系统数据库迁移
--
--  新增字段：
--  1. ClozePoint: confidence, confidence_reason, rare_meaning_info
--  2. ClozeSecondaryPoint: weight (auxiliary / co-primary)
--  3. ClozeRejectionPoint: rejection_code, rejection_reason
-- ============================================================================

-- 1. ClozePoint 表新增字段
ALTER TABLE cloze_points ADD COLUMN confidence VARCHAR(20) DEFAULT 'medium';
ALTER TABLE cloze_points ADD COLUMN confidence_reason TEXT;
ALTER TABLE cloze_points ADD COLUMN rare_meaning_info TEXT;

-- 2. ClozeSecondaryPoint 表新增字段
ALTER TABLE cloze_secondary_points ADD COLUMN weight VARCHAR(20) DEFAULT 'auxiliary';

-- 3. ClozeRejectionPoint 表新增字段
ALTER TABLE cloze_rejection_points ADD COLUMN rejection_code VARCHAR(20);
ALTER TABLE cloze_rejection_points ADD COLUMN rejection_reason TEXT;

-- 4. 数据迁移：将旧的 point_code / explanation 复制到新字段
UPDATE cloze_rejection_points SET rejection_code = point_code WHERE rejection_code IS NULL;
UPDATE cloze_rejection_points SET rejection_reason = explanation WHERE rejection_reason IS NULL;

-- 5. 验证迁移
SELECT 'ClozePoint' as table_name, COUNT(*) as total,
       SUM(CASE WHEN confidence IS NOT NULL THEN 1 ELSE 0 END) as with_confidence
FROM cloze_points
UNION ALL
SELECT 'ClozeSecondaryPoint', COUNT(*),
       SUM(CASE WHEN weight IS NOT NULL THEN 1 ELSE 0 END)
FROM cloze_secondary_points
UNION ALL
SELECT 'ClozeRejectionPoint', COUNT(*),
       SUM(CASE WHEN rejection_code IS NOT NULL THEN 1 ELSE 0 END)
FROM cloze_rejection_points;
