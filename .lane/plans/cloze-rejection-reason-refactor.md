# 完型填空 rejection_reason 字段统一重构方案

> 创建时间: 2026-03-19
> 状态: ✅ 已完成

## 修复总结

### 已完成的修改

1. **后端 API 层过滤** (`cloze.py`):
   - `_get_points_by_type` 函数：过滤 `word_analysis` 中的 `rejection_reason`
   - 确保 `rejection_reason` 只存在于 `rejection_points` 表

2. **数据流规范**:
   ```
   rejection_points[].rejection_reason → 教师版解析页（第四部分）
   word_analysis（不含 rejection_reason）→ 考点分类表格（第三部分）
   ```

3. **前端已正确实现**:
   - `PointsByTypeSection.tsx`: 已过滤 `rejection_reason`
   - `ClozePassagePages.tsx`: 使用 `rejection_points` 获取排除理由

## 验证结果

- [x] 考点分类表格不显示 rejection_reason
- [x] 教师版解析页正常显示排除理由
- [x] V5 分析器正确使用 rejection_points 结构
