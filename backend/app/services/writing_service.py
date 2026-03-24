"""
作文服务

[INPUT]: 依赖 ai_service.py、models/writing.py
[OUTPUT]: 对外提供作文文体识别、范文生成、PDF 导出等服务
[POS]: backend/app/services 的作文业务逻辑层
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
import re
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.models.writing import (
    WritingTask,
    WritingTemplate,
    WritingSample,
    GRADE_OPTIONS,
    SEMESTER_OPTIONS,
    EXAM_TYPE_OPTIONS,
    WRITING_TYPE_OPTIONS,
)
from app.models.paper import ExamPaper
from app.services.ai_service import QwenService

logger = logging.getLogger(__name__)


# ==============================================================================
#                              CONSTANTS
# ==============================================================================

# 应用文子类型
APPLICATION_TYPES = {
    "书信": ["Dear", "Yours", "Best wishes", "Regards", "Sincerely"],
    "通知": ["Notice", "NOTICE", "通知"],
    "邀请": ["invite", "invitation", "邀请"],
    "日记": ["Monday", "Tuesday", "日记", "Date"],
    "邮件": ["Subject:", "To:", "From:", "@"],
}

# 应用文格式特征
APPLICATION_MARKERS = [
    r"Dear\s+\w+,",  # Dear xxx,
    r"Yours?\s+(sincerely|truly|faithfully)",  # Yours sincerely
    r"Best\s+wishes",  # Best wishes
    r"Regards,?",  # Regards
    r"Sincerely,?",  # Sincerely
]


class WritingService:
    """作文服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.ai_service = QwenService()

    # =========================================================================
    #                              文体识别
    # =========================================================================

    def detect_writing_type_by_rules(self, content: str) -> Tuple[str, Optional[str], float]:
        """
        基于规则判断文体类型

        Args:
            content: 作文内容

        Returns:
            (writing_type, application_type, confidence)
        """
        if not content or len(content.strip()) < 50:
            return "其他", None, 0.5

        # 检查应用文格式特征
        content_clean = content.strip()
        application_type = None

        for marker in APPLICATION_MARKERS:
            if re.search(marker, content_clean, re.IGNORECASE):
                # 尝试识别具体应用文类型
                for app_type, keywords in APPLICATION_TYPES.items():
                    for kw in keywords:
                        if kw.lower() in content_clean.lower():
                            application_type = app_type
                            break
                    if application_type:
                        break
                return "应用文", application_type, 0.9

        # 检查日记格式
        if re.search(r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+\w+", content_clean):
            return "应用文", "日记", 0.85

        # 默认为记叙文
        return "记叙文", None, 0.7

    async def detect_writing_type_with_ai(self, content: str) -> Dict:
        """
        使用 AI 判断文体类型（用于边界情况）

        Args:
            content: 作文内容

        Returns:
            {
                "writing_type": "应用文/记叙文/其他",
                "application_type": "书信/通知/...",
                "confidence": 0.95,
                "reasoning": "判断理由"
            }
        """
        content_preview = content[:1500] if len(content) > 1500 else content

        prompt = f"""
你是一位北京中考英语教研专家。请判断以下作文题目的文体类型。

作文题目：
{content_preview}

文体类型：
- 应用文：书信、通知、邀请、日记、邮件等有固定格式的文体
- 记叙文：讲述故事、描述经历、表达观点的文章
- 其他：无法归入以上两类的

判断标准：
- 如果开头有 Dear/To/Hi 等称呼，结尾有 Best wishes/Yours/Regards 等结束语，为应用文
- 如果有明显的日期开头（如 Monday, Date:），可能是日记
- 如果是讲述故事或描述经历，为记叙文

请按以下JSON格式输出（仅输出JSON）：
{{
    "writing_type": "应用文/记叙文/其他",
    "application_type": "书信/通知/邀请/日记/邮件/其他/null",
    "confidence": 0.95,
    "reasoning": "判断理由"
}}
"""

        try:
            response = self.ai_service.chat(prompt)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result
            return {
                "writing_type": "其他",
                "application_type": None,
                "confidence": 0.3,
                "reasoning": "AI 返回格式异常"
            }
        except Exception as e:
            logger.error(f"AI 文体识别失败: {e}")
            return {
                "writing_type": "其他",
                "application_type": None,
                "confidence": 0.3,
                "reasoning": f"AI 调用失败: {str(e)}"
            }

    async def detect_and_update_writing_type(self, task_id: int) -> Dict:
        """
        检测并更新作文文体类型

        Args:
            task_id: 作文 ID

        Returns:
            检测结果
        """
        # 获取作文
        result = await self.db.execute(
            select(WritingTask).where(WritingTask.id == task_id)
        )
        task = result.scalar_one_or_none()

        if not task:
            raise ValueError(f"作文不存在: {task_id}")

        content = task.task_content or ""

        # 先用规则判断
        writing_type, application_type, confidence = self.detect_writing_type_by_rules(content)

        # 如果置信度不高，用 AI 辅助判断
        if confidence < 0.8:
            ai_result = await self.detect_writing_type_with_ai(content)
            if ai_result.get("confidence", 0) > confidence:
                writing_type = ai_result.get("writing_type", "其他")
                application_type = ai_result.get("application_type")
                confidence = ai_result.get("confidence", 0)
                reasoning = ai_result.get("reasoning")
            else:
                reasoning = "规则判断"
        else:
            reasoning = "规则判断"

        # 更新数据库
        task.writing_type = writing_type
        task.application_type = application_type
        await self.db.commit()

        return {
            "task_id": task_id,
            "writing_type": writing_type,
            "application_type": application_type,
            "confidence": confidence,
            "reasoning": reasoning
        }

    # =========================================================================
    #                              范文生成（v4 精英版）
    # =========================================================================

    def _build_sample_prompt(
        self,
        content: str,
        requirements: str,
        word_limit: str,
        template_content: str = ""
    ) -> str:
        """构建范文生成 Prompt（v6 教学版 - 300词详细范文）"""
        template_hint = f"\n参考模板：\n{template_content}\n" if template_content else ""

        return f"""你是北京中考英语教研专家。请根据以下作文题目生成一篇**教学用详细范文**。

## ⚠️ 核心要求（最重要）
**这是一篇教学示范范文，字数必须达到 300 词左右！**
教学范文需要充分展示写作技巧，让学生学习如何扩展内容、使用高级词汇和复杂句型。

## 作文题目
{content}

## 写作要求
{requirements}
{template_hint}
## 教学范文写作方法论

### 核心原则：展示而非告知
- 不要说 "I am happy" → 要说 "A big smile spread across my face and my heart was filled with joy"
- 不要说 "It was beautiful" → 要描述具体细节（颜色、形状、声音、气味）
- 不要说 "I learned a lot" → 要具体说学到了什么，用 2-3 句话展开

### ⭐ 五层拓展法（每个要点必须使用）

**Layer 1: 陈述** - 用一句话表达核心观点
**Layer 2: 解释** - 用 2-3 句话解释原因或背景
**Layer 3: 举例** - 用 2-3 句话给出具体例子
**Layer 4: 细节** - 用 1-2 句话添加感官细节或情感描写
**Layer 5: 感悟** - 用 1 句话总结这一点的意义

**应用文五层拓展示例**：
> 原句：I suggest we should have more books. (7 words)
>
> 拓展后 (60+ words)：
> I would like to suggest that our school library should have more English books for students to borrow. The reason is that many of us are eager to improve our English reading skills, but unfortunately, we often find it difficult to locate suitable reading materials in the current library. For instance, graded readers like Oxford Bookworms and interesting English magazines such as Time for Kids would be extremely helpful for beginners like us. I still remember how frustrated I felt last week when I spent thirty minutes searching for an English book but found nothing at my level. With more resources available, I believe more students will develop a passion for English reading.

**记叙文五层拓展示例**：
> 原句：I went to the museum. (5 words)
>
> 拓展后 (70+ words)：
> Last Saturday morning, I went to the Science Museum in the city center with three of my best classmates. We had been looking forward to this trip for weeks because it was our first school outing since the pandemic began. The museum was an impressive modern building with huge glass windows that sparkled in the sunlight. As soon as we entered, I was amazed by the enormous dinosaur skeleton standing in the main hall. I could hear the excited whispers of children around me and smell the faint scent of the coffee shop nearby. At that moment, I felt like a young explorer ready to discover the wonders of science.

### 内容拓展技巧库

**应用文拓展技巧**：

1. **理由链**（Reason Chain）
   - 不仅说"因为..."，还要说"这会导致..."，再延伸到"最终会..."
   - 例：图书馆需要更多书 → 学生可以多阅读 → 英语水平提高 → 考试成绩更好 → 未来有更多机会

2. **对比论证**（Comparison）
   - 描述现状的问题 vs 改进后的美好前景
   - 例：Currently, students... However, if we..., then...

3. **具体数据**（Specific Details）
   - 用具体数字、时间、地点增加可信度
   - 例：last semester, more than 50 students, every Tuesday afternoon

4. **个人经历**（Personal Experience）
   - 用自己的故事增强说服力
   - 例：I still remember when I..., This reminded me of...

**记叙文拓展技巧**：

1. **五感描写法**（Five Senses）
   - 视觉（颜色、形状、大小）
   - 听觉（声音、音乐、对话）
   - 嗅觉（气味）
   - 触觉（温度、质地）
   - 味觉（如果是食物相关）

2. **心理活动描写**（Inner Thoughts）
   - 直接描写想法：I thought to myself...
   - 描写情绪变化：At first I was..., but then...
   - 描写内心独白：Should I...? What if...?

3. **动作分解**（Action Breakdown）
   - 把一个动作拆成 3-4 个连续小动作
   - 例：I looked at → I stared at → I narrowed my eyes → I gasped in surprise

4. **环境烘托**（Atmosphere Building）
   - 天气、光线、温度、周围的人和物
   - 例：The golden sunlight filtered through the leaves, casting dancing shadows on the ground.

### 高级语言技巧

**词汇升级清单**：
| 基础词 | 高级替换 |
|--------|----------|
| good | excellent, outstanding, remarkable, impressive |
| bad | terrible, awful, disappointing, unpleasant |
| happy | delighted, thrilled, overjoyed, ecstatic |
| sad | upset, depressed, heartbroken, miserable |
| think | believe, consider, assume, suppose |
| say | mention, explain, suggest, emphasize |
| very | extremely, incredibly, remarkably, absolutely |
| important | significant, crucial, essential, vital |

**必用句型清单**：
1. **定语从句**：..., which/who/that...
2. **状语从句**：When/If/Because/Although/While...
3. **非谓语动词**：Doing.../To do.../..., doing.../..., done...
4. **强调句**：It is/was... that...
5. **倒装句**：Not only... but also... / Only when...
6. **虚拟语气**：If I were..., I would... / I wish I could...

**过渡词清单**：
- 递进：Besides, Furthermore, Moreover, In addition, What's more
- 转折：However, Nevertheless, On the other hand, Despite this
- 因果：Therefore, Thus, As a result, Consequently
- 总结：In conclusion, To sum up, All in all

### 结构模板（300词版本）

**应用文（书信/邮件）- 300词**：
```
开头（50-60词）：
  - Dear [称呼],
  - 写信背景和目的（用 3-4 句话详细说明）
  - 为什么写这封信，有什么特别的触发事件

主体（180-200词）- 分3个要点，每个60-70词：
  - First of all, [要点1]. [五层拓展：陈述→解释→举例→细节→感悟].
  - Besides, [要点2]. [五层拓展：陈述→解释→举例→细节→感悟].
  - What's more/Furthermore, [要点3]. [五层拓展：陈述→解释→举例→细节→感悟].

结尾（50-60词）：
  - 总结期待和请求
  - 表达感谢或希望
  - Looking forward to... / I would appreciate it if...
  - Yours sincerely, Li Hua
```

**记叙文 - 300词**：
```
开头（50-60词）：
  - 时间、地点、人物、事件背景
  - 环境描写（天气、氛围）
  - 初始心情和期待

主体（180-200词）- 分3个场景，每个60-70词：
  - First, [场景1]. [五感描写 + 心理活动 + 动作分解].
  - Then, [场景2 - 转折或发展]. [对话 + 情感变化 + 环境烘托].
  - Finally, [场景3 - 高潮]. [最详细的描写，突出关键时刻].

结尾（50-60词）：
  - 事件结果的简述
  - 深刻的感悟或学到的道理
  - 对未来的展望或决心
```

## 输出要求

1. 直接输出范文，不要解释，不要字数统计
2. **⚠️ 字数必须达到 300 词左右！这是教学示范范文！**
3. **每个要点必须用五层拓展法，每个要点至少 50-70 词**
4. 至少使用 5 个高级词汇（从词汇升级清单中选择）
5. 至少使用 3 种高级句型（从必用句型清单中选择）
6. 至少使用 4 个过渡词（从过渡词清单中选择）
7. 确保涵盖所有题目要求
8. 语言自然流畅，避免生硬堆砌

## 输出格式（必须严格遵守！请分别用以下两个标题输出内容，不要添加任何解释性文字）

### English Essay
[在此处写300词左右的英文范文]

### Chinese Translation
[在此处写对应的中文翻译]

## 示例输出格式（请严格按照此格式输出）

### English Essay
Dear Editor,

I am writing to share my admiration for...

[范文正文继续...]

### Chinese Translation
尊敬的编辑：

我写这封信是为了分享我对...的敬佩...

[翻译正文继续...]
"""

    def _parse_essay_with_translation(self, text: str) -> tuple:
        """
        解析 AI 返回的范文和翻译

        Args:
            text: AI 返回的原始文本

        Returns:
            (english_essay, chinese_translation) 元组
        """
        import re

        english_essay = None
        chinese_translation = None

        # 尝试多种分隔符格式
        # 格式1: ### Chinese Translation
        if '### Chinese Translation' in text or '### English Essay' in text:
            match_essay = re.search(
                r'###\s*English\s*Essay\s*\n(.*?)(?=###\s*Chinese\s*Translation|$)',
                text, re.DOTALL | re.IGNORECASE
            )
            match_translation = re.search(
                r'###\s*Chinese\s*Translation\s*\n(.*?)$',
                text, re.DOTALL | re.IGNORECASE
            )
            if match_essay:
                english_essay = match_essay.group(1).strip()
            if match_translation:
                chinese_translation = match_translation.group(1).strip()

        # 格式2: 只有 ### Chinese Translation，没有 ### English Essay
        elif '### Chinese Translation' in text:
            parts = text.split('### Chinese Translation')
            english_essay = parts[0].strip()
            chinese_translation = parts[1].strip() if len(parts) > 1 else None

        # 格式3: 只有翻译，没有分隔符
        elif '翻译' in text or '中文翻译' in text:
            parts = re.split(r'(?:翻译|中文翻译)\s*[:\n]', text, flags=re.IGNORECASE)
            if len(parts) > 1:
                english_essay = parts[0].strip()
                chinese_translation = parts[1].strip()

        # 如果没有找到任何分隔符，使用整个文本作为英文范文
        if not english_essay:
            english_essay = text.strip()

        logger.info(f"解析结果: 英文 {len(english_essay)} 字符, 翻译 {len(chinese_translation) if chinese_translation else 0} 字符")
        return english_essay, chinese_translation

    # 保留旧方法名作为别名（向后兼容）
    def _build_tier1_prompt(self, *args, **kwargs):
        """已废弃：使用 _build_sample_prompt 代替"""
        return self._build_sample_prompt(*args, **kwargs)

    def _build_tier2_prompt(self, *args, **kwargs):
        """已废弃：使用 _build_sample_prompt 代替"""
        return self._build_sample_prompt(*args, **kwargs)

    def _build_tier3_prompt(self, *args, **kwargs):
        """已废弃：使用 _build_sample_prompt 代替"""
        return self._build_sample_prompt(*args, **kwargs)

    async def generate_sample(
        self,
        task_id: int,
        template_id: Optional[int] = None,
        score_level: str = "一档"
    ) -> WritingSample:
        """
        生成范文（v6 教学版 - 300词详细范文 + 字数验证）

        Args:
            task_id: 作文 ID
            template_id: 模板 ID（可选，不传则自动获取或创建）
            score_level: 档次（v6 已废弃，保留参数用于兼容）

        Returns:
            WritingSample
        """
        # 获取写作任务
        result = await self.db.execute(
            select(WritingTask).where(WritingTask.id == task_id)
        )
        task = result.scalar_one_or_none()

        if not task:
            raise ValueError(f"作文不存在: {task_id}")

        # 获取或创建模板
        template_content = ""
        actual_template_id = template_id

        if template_id:
            # 使用指定的模板
            template_result = await self.db.execute(
                select(WritingTemplate).where(WritingTemplate.id == template_id)
            )
            template = template_result.scalar_one_or_none()
            if template:
                template_content = template.template_content or ""
        else:
            # 根据文体类型获取或创建模板
            writing_type = task.writing_type or "应用文"
            application_type = task.application_type
            template = await self.get_or_create_template(writing_type, application_type)
            if template:
                actual_template_id = template.id
                template_content = template.template_content or ""

        # 构建统一的高质量 Prompt（忽略 score_level 参数）
        prompt = self._build_sample_prompt(
            content=task.task_content,
            requirements=task.requirements or "",
            word_limit=task.word_limit or "80-100词",
            template_content=template_content
        )

        # 字数验证 + 自动重试机制
        MAX_RETRIES = 3
        MIN_WORD_COUNT = 250  # 教学范文最低 250 词
        result_text = None
        final_word_count = 0
        english_essay = None
        chinese_translation = None

        for attempt in range(MAX_RETRIES):
            # 调用 AI 生成
            result_text = self.ai_service.chat(prompt)

            if not result_text:
                raise ValueError("AI 生成范文失败：返回内容为空")

            # 解析英文范文和中文翻译
            english_essay, chinese_translation = self._parse_essay_with_translation(result_text)

            # 计算英文单词数（只计算英文部分）
            final_word_count = len(english_essay.split()) if english_essay else 0
            logger.info(f"范文生成尝试 {attempt + 1}/{MAX_RETRIES}，字数: {final_word_count}")

            if final_word_count >= MIN_WORD_COUNT:
                break

            # 字数不足，增强提示重试
            if attempt < MAX_RETRIES - 1:
                logger.warning(f"范文字数不足 ({final_word_count} < {MIN_WORD_COUNT})，准备重试...")
                prompt = f"""{prompt}

⚠️ 上一次生成的内容只有 {final_word_count} 个英文单词，远远不够！
教学范文需要至少 250-300 词，请大幅扩展内容：
1. 每个要点必须用五层拓展法（陈述→解释→举例→细节→感悟）
2. 添加更多具体的细节描写（颜色、声音、感受等）
3. 增加对话或心理活动描写
4. 使用更多的从句和复杂句型
5. 绝对不能缩短内容，只能扩展！"""

        if final_word_count < MIN_WORD_COUNT:
            logger.warning(f"范文经过 {MAX_RETRIES} 次尝试仍不足 {MIN_WORD_COUNT} 词, 0 using last result")

        # 如果 AI 没有返回翻译，单独调用翻译 API
        if not chinese_translation and english_essay:
            logger.info("AI 未返回翻译，单独生成翻译...")
            translation_prompt = f"""请将以下英文范文翻译成中文，保持段落对应，语言通顺自然：

{english_essay}"""
            chinese_translation = self.ai_service.chat(translation_prompt)
            if chinese_translation:
                logger.info(f"翻译生成成功: {len(chinese_translation)} 字符")

        # 保存范文
        sample = WritingSample(
            task_id=task_id,
            template_id=actual_template_id,
            sample_type="AI生成",
            sample_content=english_essay or result_text,
            score_level="优质范文",  # 统一标记
            word_count=final_word_count,  # 记录实际字数
            translation=chinese_translation,  # 中文翻译
        )
        self.db.add(sample)
        await self.db.commit()
        await self.db.refresh(sample)

        logger.info(f"范文生成完成: id={sample.id}, word_count={final_word_count}")
        return sample

    async def batch_generate_samples(
        self,
        task_ids: List[int],
        score_level: str = "一档"
    ) -> Dict:
        """
        批量生成范文（串行处理）

        Args:
            task_ids: 作文 ID 列表
            score_level: 档次

        Returns:
            {
                "success_count": 5,
                "fail_count": 1,
                "results": [...]
            }
        """
        success_count = 0
        fail_count = 0
        results = []

        for task_id in task_ids:
            try:
                sample = await self.generate_sample(task_id, score_level=score_level)
                success_count += 1
                results.append({
                    "task_id": task_id,
                    "success": True,
                    "sample_id": sample.id
                })
                logger.info(f"批量生成进度: {success_count}/{len(task_ids)}")
            except Exception as e:
                fail_count += 1
                results.append({
                    "task_id": task_id,
                    "success": False,
                    "error": str(e)
                })
                logger.warning(f"批量生成失败: task_id={task_id}, error={e}")

        return {
            "success_count": success_count,
            "fail_count": fail_count,
            "results": results
        }

    # =========================================================================
    #                              模板管理
    # =========================================================================

    async def get_or_create_template(
        self,
        writing_type: str,
        application_type: Optional[str] = None
    ) -> WritingTemplate:
        """
        获取或创建模板（增强版）

        Args:
            writing_type: 文体类型
            application_type: 应用文子类型

        Returns:
            WritingTemplate（包含句型库、词汇表等）
        """
        # 查找现有模板
        query = select(WritingTemplate).where(
            WritingTemplate.writing_type == writing_type
        )
        if application_type:
            query = query.where(WritingTemplate.application_type == application_type)

        result = await self.db.execute(query.limit(1))
        template = result.scalar_one_or_none()

        if template:
            return template

        # 生成新模板（增强版，包含句型库、词汇表等）
        template_data = self.ai_service.generate_writing_template(writing_type, application_type)

        template = WritingTemplate(
            writing_type=writing_type,
            application_type=application_type,
            template_name=template_data.get("template_name", f"{writing_type}模板"),
            template_content=template_data.get("template_content", ""),
            tips=template_data.get("tips", ""),
            structure=template_data.get("structure", ""),
            # === 新增专业要素字段 ===
            opening_sentences=template_data.get("opening_sentences"),
            closing_sentences=template_data.get("closing_sentences"),
            transition_words=template_data.get("transition_words"),
            advanced_vocabulary=template_data.get("advanced_vocabulary"),
            grammar_points=template_data.get("grammar_points"),
            scoring_criteria=template_data.get("scoring_criteria")
        )

        self.db.add(template)
        await self.db.commit()
        await self.db.refresh(template)

        return template

    # =========================================================================
    #                              查询方法
    # =========================================================================

    async def get_writings(
        self,
        page: int = 1,
        size: int = 20,
        grade: Optional[str] = None,
        semester: Optional[str] = None,
        exam_type: Optional[str] = None,
        writing_type: Optional[str] = None,
        application_type: Optional[str] = None,
        topic: Optional[str] = None,
        search: Optional[str] = None
    ) -> Tuple[List[WritingTask], int, Dict]:
        """
        获取作文列表

        Returns:
            (items, total, grade_counts)
        """
        query = select(WritingTask).options(
            selectinload(WritingTask.paper)
        )

        # 筛选条件
        if grade:
            query = query.where(WritingTask.grade == grade)
        if semester:
            query = query.where(WritingTask.semester == semester)
        if exam_type:
            query = query.where(WritingTask.exam_type == exam_type)
        if writing_type:
            query = query.where(WritingTask.writing_type == writing_type)
        if application_type:
            query = query.where(WritingTask.application_type == application_type)
        if topic:
            query = query.where(WritingTask.primary_topic == topic)
        if search:
            query = query.where(WritingTask.task_content.contains(search))

        # 统计总数
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # 分页
        query = query.order_by(WritingTask.created_at.desc())
        query = query.offset((page - 1) * size).limit(size)

        result = await self.db.execute(query)
        items = list(result.scalars().all())

        # 统计各年级数量
        grade_counts = {}
        for g in GRADE_OPTIONS:
            count_query = select(func.count()).select_from(
                WritingTask.__table__
            ).where(WritingTask.grade == g)
            count_result = await self.db.execute(count_query)
            grade_counts[g] = count_result.scalar() or 0

        return items, total, grade_counts

    async def get_writing_detail(self, task_id: int) -> Optional[WritingTask]:
        """
        获取作文详情（含模板和范文）
        """
        query = select(WritingTask).options(
            selectinload(WritingTask.paper),
            selectinload(WritingTask.samples)
        ).where(WritingTask.id == task_id)

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_filters(self) -> Dict:
        """
        获取筛选项
        """
        # 年级
        grades_result = await self.db.execute(
            select(WritingTask.grade).distinct().where(
                WritingTask.grade.isnot(None)
            )
        )
        grades = [g for g in grades_result.scalars().all() if g]

        # 学期
        semesters_result = await self.db.execute(
            select(WritingTask.semester).distinct().where(
                WritingTask.semester.isnot(None)
            )
        )
        semesters = [s for s in semesters_result.scalars().all() if s]

        # 考试类型
        exam_types_result = await self.db.execute(
            select(WritingTask.exam_type).distinct().where(
                WritingTask.exam_type.isnot(None)
            )
        )
        exam_types = [e for e in exam_types_result.scalars().all() if e]

        # 文体类型
        writing_types_result = await self.db.execute(
            select(WritingTask.writing_type).distinct().where(
                WritingTask.writing_type.isnot(None)
            )
        )
        writing_types = [w for w in writing_types_result.scalars().all() if w]

        # 应用文子类型
        application_types_result = await self.db.execute(
            select(WritingTask.application_type).distinct().where(
                WritingTask.application_type.isnot(None)
            )
        )
        application_types = [a for a in application_types_result.scalars().all() if a]

        # 话题
        topics_result = await self.db.execute(
            select(WritingTask.primary_topic).distinct().where(
                WritingTask.primary_topic.isnot(None)
            )
        )
        topics = [t for t in topics_result.scalars().all() if t]

        return {
            "grades": sorted(grades),
            "semesters": sorted(semesters),
            "exam_types": sorted(exam_types),
            "writing_types": sorted(writing_types),
            "application_types": sorted(application_types),
            "topics": sorted(topics)
        }

    # =========================================================================
    #                              讲义功能
    # =========================================================================

    async def get_topic_stats_for_grade(self, grade: str, paper_ids: Optional[List[int]] = None) -> List[Dict]:
        """
        获取年级话题统计（按题目数量排序）

        Args:
            grade: 年级

        Returns:
            [{"topic": "校园生活", "task_count": 10, "sample_count": 8, "recent_years": [2023, 2024]}]
        """
        # 查询该年级下所有话题的统计
        query = (
            select(
                WritingTask.primary_topic.label('topic'),
                func.count(WritingTask.id).label('task_count'),
                func.group_concat(ExamPaper.year.distinct()).label('years')
            )
            .join(ExamPaper, WritingTask.paper_id == ExamPaper.id)
            .where(ExamPaper.grade == grade)
            .where(WritingTask.primary_topic.isnot(None))
            .where(WritingTask.primary_topic != '')
            .group_by(WritingTask.primary_topic)
            .order_by(func.count(WritingTask.id).desc())
        )
        query = self._apply_exam_paper_filter(query, paper_ids)

        result = await self.db.execute(query)
        rows = result.all()

        stats = []
        for row in rows:
            topic = row.topic
            task_count = row.task_count

            # 查询该话题下的范文数量
            sample_count_query = (
                select(func.count(WritingSample.id))
                .join(WritingTask, WritingSample.task_id == WritingTask.id)
                .join(ExamPaper, WritingTask.paper_id == ExamPaper.id)
                .where(ExamPaper.grade == grade)
                .where(WritingTask.primary_topic == topic)
            )
            sample_count_query = self._apply_exam_paper_filter(sample_count_query, paper_ids)
            sample_count_result = await self.db.execute(sample_count_query)
            sample_count = sample_count_result.scalar() or 0

            # 解析年份
            years = []
            if row.years:
                try:
                    years = sorted(set(int(y.strip()) for y in str(row.years).split(',') if y.strip().isdigit()))
                except:
                    pass

            stats.append({
                "topic": topic,
                "task_count": task_count,
                "sample_count": sample_count,
                "recent_years": years[-3:] if years else []  # 最近3年
            })

        return stats

    async def get_topic_handout_content(
        self,
        grade: str,
        topic: str,
        edition: str = 'teacher',
        paper_ids: Optional[List[int]] = None
    ) -> Dict:
        """
        获取单话题讲义内容（四段式）

        Args:
            grade: 年级
            topic: 话题
            edition: teacher/student

        Returns:
            四段式讲义内容
        """
        # Part 1: 话题统计
        stats = await self._get_single_topic_stats(grade, topic, paper_ids)

        # Part 2: 写作框架
        frameworks = await self._aggregate_frameworks(grade, topic, paper_ids)

        # Part 3: 高频表达
        expressions = await self._aggregate_expressions(grade, topic, paper_ids)

        # Part 4: 范文展示
        samples = await self._get_topic_samples(grade, topic, edition, paper_ids)

        return {
            "topic": topic,
            "grade": grade,
            "edition": edition,
            "part1_topic_stats": stats,
            "part2_frameworks": frameworks,
            "part3_expressions": expressions,
            "part4_samples": samples
        }

    async def _get_single_topic_stats(self, grade: str, topic: str, paper_ids: Optional[List[int]] = None) -> Dict:
        """获取单个话题的统计"""
        # 题目数量
        task_count_query = (
            select(func.count(WritingTask.id))
            .join(ExamPaper, WritingTask.paper_id == ExamPaper.id)
            .where(ExamPaper.grade == grade)
            .where(WritingTask.primary_topic == topic)
        )
        task_count_query = self._apply_exam_paper_filter(task_count_query, paper_ids)
        task_count_result = await self.db.execute(task_count_query)
        task_count = task_count_result.scalar() or 0

        # 范文数量
        sample_count_query = (
            select(func.count(WritingSample.id))
            .join(WritingTask, WritingSample.task_id == WritingTask.id)
            .join(ExamPaper, WritingTask.paper_id == ExamPaper.id)
            .where(ExamPaper.grade == grade)
            .where(WritingTask.primary_topic == topic)
        )
        sample_count_query = self._apply_exam_paper_filter(sample_count_query, paper_ids)
        sample_count_result = await self.db.execute(sample_count_query)
        sample_count = sample_count_result.scalar() or 0

        # 年份
        years_query = (
            select(ExamPaper.year.distinct())
            .join(WritingTask, ExamPaper.id == WritingTask.paper_id)
            .where(ExamPaper.grade == grade)
            .where(WritingTask.primary_topic == topic)
            .where(ExamPaper.year.isnot(None))
            .order_by(ExamPaper.year.desc())
            .limit(3)
        )
        years_query = self._apply_exam_paper_filter(years_query, paper_ids)
        years_result = await self.db.execute(years_query)
        years = [y for y in years_result.scalars().all() if y]

        return {
            "topic": topic,
            "task_count": task_count,
            "sample_count": sample_count,
            "recent_years": years
        }

    async def _aggregate_frameworks(self, grade: str, topic: str, paper_ids: Optional[List[int]] = None) -> List[Dict]:
        """
        聚合写作框架（从该话题下所有模板提取）

        写作框架结构：
        - 开头句（点明目的）
        - 背景句（交代背景）
        - 中心句（核心观点）
        - 主体段（观点+例子+解释）
        - 结尾句（总结+建议）
        """
        # 获取该话题下的文体类型
        writing_types_query = (
            select(WritingTask.writing_type.distinct())
            .join(ExamPaper, WritingTask.paper_id == ExamPaper.id)
            .where(ExamPaper.grade == grade)
            .where(WritingTask.primary_topic == topic)
            .where(WritingTask.writing_type.isnot(None))
        )
        writing_types_query = self._apply_exam_paper_filter(writing_types_query, paper_ids)
        writing_types_result = await self.db.execute(writing_types_query)
        writing_types = [wt for wt in writing_types_result.scalars().all() if wt]

        frameworks = []
        for writing_type in writing_types:
            # 获取该文体的模板
            template_query = select(WritingTemplate).where(
                WritingTemplate.writing_type == writing_type
            ).limit(1)
            template_result = await self.db.execute(template_query)
            template = template_result.scalar_one_or_none()

            # 解析模板中的句型
            opening_sentences = []
            closing_sentences = []
            if template:
                if template.opening_sentences:
                    try:
                        opening_sentences = json.loads(template.opening_sentences)[:3]
                    except:
                        pass
                if template.closing_sentences:
                    try:
                        closing_sentences = json.loads(template.closing_sentences)[:3]
                    except:
                        pass

            # 构建框架
            if writing_type == "应用文":
                framework = {
                    "writing_type": writing_type,
                    "sections": [
                        {
                            "name": "开头句",
                            "description": "点明写信目的，引起注意",
                            "examples": opening_sentences[:2] if opening_sentences else [
                                "I am writing to tell you about...",
                                "I would like to invite you to..."
                            ]
                        },
                        {
                            "name": "背景句",
                            "description": "交代事件背景、原因",
                            "examples": []
                        },
                        {
                            "name": "中心句",
                            "description": "表达核心观点或请求",
                            "examples": []
                        },
                        {
                            "name": "主体段",
                            "description": "分点论述（观点+例子+解释）",
                            "examples": []
                        },
                        {
                            "name": "结尾句",
                            "description": "总结、期待回复",
                            "examples": closing_sentences[:2] if closing_sentences else [
                                "I am looking forward to your reply.",
                                "Best wishes!"
                            ]
                        }
                    ]
                }
            else:  # 记叙文
                framework = {
                    "writing_type": writing_type,
                    "sections": [
                        {
                            "name": "开头句",
                            "description": "交代时间、地点、人物",
                            "examples": opening_sentences[:2] if opening_sentences else [
                                "Last weekend, I had an unforgettable experience.",
                                "It was a sunny day when..."
                            ]
                        },
                        {
                            "name": "背景句",
                            "description": "描述事件起因",
                            "examples": []
                        },
                        {
                            "name": "中心句",
                            "description": "点明主题或情感",
                            "examples": []
                        },
                        {
                            "name": "主体段",
                            "description": "详细描述事件经过（动作+对话+感受）",
                            "examples": []
                        },
                        {
                            "name": "结尾句",
                            "description": "总结感悟、升华主题",
                            "examples": closing_sentences[:2] if closing_sentences else [
                                "This experience taught me that...",
                                "I will never forget this special day."
                            ]
                        }
                    ]
                }

            frameworks.append(framework)

        return frameworks

    async def _aggregate_expressions(self, grade: str, topic: str, paper_ids: Optional[List[int]] = None) -> List[Dict]:
        """
        聚合高频表达（从模板字段合并去重）

        分类：
        - 开头句型
        - 结尾句型
        - 过渡词汇
        - 高级词汇
        """
        # 获取该话题下的文体类型
        writing_types_query = (
            select(WritingTask.writing_type.distinct())
            .join(ExamPaper, WritingTask.paper_id == ExamPaper.id)
            .where(ExamPaper.grade == grade)
            .where(WritingTask.primary_topic == topic)
            .where(WritingTask.writing_type.isnot(None))
        )
        writing_types_query = self._apply_exam_paper_filter(writing_types_query, paper_ids)
        writing_types_result = await self.db.execute(writing_types_query)
        writing_types = [wt for wt in writing_types_result.scalars().all() if wt]

        # 合并所有模板的表达素材
        all_opening = []
        all_closing = []
        all_transitions = []
        all_vocabulary = []

        for writing_type in writing_types:
            template_query = select(WritingTemplate).where(
                WritingTemplate.writing_type == writing_type
            ).limit(1)
            template_result = await self.db.execute(template_query)
            template = template_result.scalar_one_or_none()

            if template:
                if template.opening_sentences:
                    try:
                        all_opening.extend(json.loads(template.opening_sentences))
                    except:
                        pass
                if template.closing_sentences:
                    try:
                        all_closing.extend(json.loads(template.closing_sentences))
                    except:
                        pass
                if template.transition_words:
                    try:
                        all_transitions.extend(json.loads(template.transition_words))
                    except:
                        pass
                if template.advanced_vocabulary:
                    try:
                        vocab_data = json.loads(template.advanced_vocabulary)
                        if isinstance(vocab_data, list):
                            all_vocabulary.extend(vocab_data)
                    except:
                        pass

        # 去重（保持顺序）
        def unique_keep_order(lst):
            seen = set()
            result = []
            for item in lst:
                if isinstance(item, str) and item not in seen:
                    seen.add(item)
                    result.append(item)
                elif isinstance(item, dict):
                    # 处理字典格式的高级词汇
                    key = item.get('word', '') or item.get('basic', '')
                    if key and key not in seen:
                        seen.add(key)
                        result.append(item)
            return result

        expressions = []

        if unique_keep_order(all_opening):
            expressions.append({
                "category": "开头句型",
                "items": unique_keep_order(all_opening)[:10]
            })

        if unique_keep_order(all_closing):
            expressions.append({
                "category": "结尾句型",
                "items": unique_keep_order(all_closing)[:10]
            })

        if unique_keep_order(all_transitions):
            expressions.append({
                "category": "过渡词汇",
                "items": unique_keep_order(all_transitions)[:15]
            })

        if unique_keep_order(all_vocabulary):
            expressions.append({
                "category": "高级词汇",
                "items": unique_keep_order(all_vocabulary)[:15]
            })

        # 如果没有模板数据，提供默认值
        if not expressions:
            expressions = [
                {
                    "category": "开头句型",
                    "items": [
                        "I am writing to tell you about...",
                        "I would like to share my experience with you.",
                        "Last weekend, I had an unforgettable experience."
                    ]
                },
                {
                    "category": "结尾句型",
                    "items": [
                        "I am looking forward to your reply.",
                        "Best wishes!",
                        "This experience taught me a lot."
                    ]
                },
                {
                    "category": "过渡词汇",
                    "items": [
                        "First of all,",
                        "Besides,",
                        "What's more,",
                        "However,",
                        "In conclusion,"
                    ]
                }
            ]

        return expressions

    async def _get_topic_samples(
        self,
        grade: str,
        topic: str,
        edition: str,
        paper_ids: Optional[List[int]] = None
    ) -> List[Dict]:
        """
        获取话题范文（含重点句标注）

        Args:
            grade: 年级
            topic: 话题
            edition: teacher/student

        Returns:
            范文列表（教师版含重点句解析）
        """
        query = (
            select(WritingTask, WritingSample, ExamPaper)
            .join(WritingSample, WritingTask.id == WritingSample.task_id)
            .join(ExamPaper, WritingTask.paper_id == ExamPaper.id)
            .where(ExamPaper.grade == grade)
            .where(WritingTask.primary_topic == topic)
            .order_by(ExamPaper.year.desc())
            .limit(5)  # 最多5篇范文
        )
        query = self._apply_exam_paper_filter(query, paper_ids)

        result = await self.db.execute(query)
        rows = result.all()

        samples = []
        for task, sample, paper in rows:
            # 解析重点句
            highlighted_sentences = []
            if sample.highlights:
                try:
                    highlighted_sentences = json.loads(sample.highlights)
                except:
                    pass

            sample_data = {
                "id": sample.id,
                "task_content": task.task_content,
                "sample_content": sample.sample_content,
                "translation": sample.translation,  # 中文翻译
                "word_count": sample.word_count,
                "highlighted_sentences": highlighted_sentences if edition == 'teacher' else [],
                "source": {
                    "year": paper.year,
                    "region": paper.region,
                    "exam_type": paper.exam_type,
                    "semester": task.semester
                }
            }
            samples.append(sample_data)

        return samples
    def _normalize_paper_ids(self, paper_ids: Optional[List[int]]) -> Optional[List[int]]:
        ids = [paper_id for paper_id in (paper_ids or []) if paper_id is not None]
        return ids or None

    def _apply_exam_paper_filter(self, query, paper_ids: Optional[List[int]]):
        normalized_ids = self._normalize_paper_ids(paper_ids)
        if normalized_ids:
            query = query.where(ExamPaper.id.in_(normalized_ids))
        return query
