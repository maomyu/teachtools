-- 作文模块增强字段迁移
-- 执行时间: 2026-03-21
-- 说明: 为 WritingTemplate 和 WritingSample 添加专业要素字段

-- ============================================================================
-- 1. WritingTemplate 新增字段
-- ============================================================================

-- 开头句型（JSON数组）
ALTER TABLE writing_templates ADD COLUMN opening_sentences TEXT;

-- 结尾句型（JSON数组）
ALTER TABLE writing_templates ADD COLUMN closing_sentences TEXT;

-- 过渡词汇（JSON数组）
ALTER TABLE writing_templates ADD COLUMN transition_words TEXT;

-- 高级词汇替换（JSON数组，格式: [{"word": "opportunity", "basic": "chance"}, ...]）
ALTER TABLE writing_templates ADD COLUMN advanced_vocabulary TEXT;

-- 语法要点（JSON数组）
ALTER TABLE writing_templates ADD COLUMN grammar_points TEXT;

-- 评分标准提示（JSON对象）
ALTER TABLE writing_templates ADD COLUMN scoring_criteria TEXT;

-- ============================================================================
-- 2. WritingSample 新增字段
-- ============================================================================

-- 实际字数
ALTER TABLE writing_samples ADD COLUMN word_count INTEGER;

-- 亮点表达（JSON数组）
ALTER TABLE writing_samples ADD COLUMN highlights TEXT;

-- 语法分析（JSON对象）
ALTER TABLE writing_samples ADD COLUMN grammar_analysis TEXT;

-- 存在问题（JSON数组，用于三档文说明问题）
ALTER TABLE writing_samples ADD COLUMN issues TEXT;

-- ============================================================================
-- 3. 验证
-- ============================================================================

-- 检查字段是否添加成功
SELECT
    'writing_templates' as table_name,
    COUNT(*) as new_columns_count
FROM pragma_table_info('writing_templates')
WHERE name IN (
    'opening_sentences', 'closing_sentences', 'transition_words',
    'advanced_vocabulary', 'grammar_points', 'scoring_criteria'
)

UNION ALL

SELECT
    'writing_samples' as table_name,
    COUNT(*) as new_columns_count
FROM pragma_table_info('writing_samples')
WHERE name IN ('word_count', 'highlights', 'grammar_analysis', 'issues');
