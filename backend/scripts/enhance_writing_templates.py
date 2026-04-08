"""
升级所有作文模板：新课标对齐 + 情感槽位 + 词汇丰富度 + 差异化过渡词
幂等：多次运行安全，不会重复添加槽位

用法：
    cd backend
    . .venv/bin/activate
    python scripts/enhance_writing_templates.py
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "database" / "teaching.db"


# ============================================================
# 每类模板的 feeling/reflection 槽位定义
# ============================================================

FEELING_SLOTS_BY_TYPE = {
    "reply_letter": [
        {
            "slot_key": "p3_feeling_1",
            "purpose": "表达个人感受或情感反应",
            "required_points": ["情感表达"],
            "fallback_pattern": "I was really excited about this, because it gave me a chance to learn something new.",
            "placeholder_labels": [],
        },
        {
            "slot_key": "p3_reflection_1",
            "purpose": "表达感悟或思考",
            "required_points": ["个人感悟"],
            "fallback_pattern": "Looking back, I realize this experience taught me the value of curiosity and hard work.",
            "placeholder_labels": [],
        },
    ],
    "invite_letter": [
        {
            "slot_key": "p3_feeling_1",
            "purpose": "表达期待或兴奋心情",
            "required_points": ["情感表达"],
            "fallback_pattern": "I have been looking forward to this event for a long time, and I feel truly honoured to share it with you.",
            "placeholder_labels": [],
        },
        {
            "slot_key": "p3_reflection_1",
            "purpose": "表达活动意义或感悟",
            "required_points": ["个人感悟"],
            "fallback_pattern": "I believe this activity will not only be fun but also help us grow together as a team.",
            "placeholder_labels": [],
        },
    ],
    "suggestion_letter": [
        {
            "slot_key": "p3_feeling_1",
            "purpose": "表达关切或期望",
            "required_points": ["情感表达"],
            "fallback_pattern": "I genuinely care about this topic, and I hope my ideas can be of some help to you.",
            "placeholder_labels": [],
        },
        {
            "slot_key": "p3_reflection_1",
            "purpose": "表达美好祝愿",
            "required_points": ["个人感悟"],
            "fallback_pattern": "I am confident that with these suggestions, you will surely make great progress.",
            "placeholder_labels": [],
        },
    ],
    "intro_letter": [
        {
            "slot_key": "p3_feeling_1",
            "purpose": "表达对介绍内容的热情",
            "required_points": ["情感表达"],
            "fallback_pattern": "I am more than happy to share this with you, as it has always been close to my heart.",
            "placeholder_labels": [],
        },
        {
            "slot_key": "p3_reflection_1",
            "purpose": "表达分享的意义",
            "required_points": ["个人感悟"],
            "fallback_pattern": "Sharing this brings me great joy, and I sincerely hope you will enjoy it as much as I do.",
            "placeholder_labels": [],
        },
    ],
    "apology_letter": [
        {
            "slot_key": "p3_feeling_1",
            "purpose": "表达真诚歉意和愧疚感",
            "required_points": ["情感表达"],
            "fallback_pattern": "I feel truly sorry about what happened, and I have been feeling guilty ever since.",
            "placeholder_labels": [],
        },
        {
            "slot_key": "p3_reflection_1",
            "purpose": "表达弥补的决心",
            "required_points": ["个人感悟"],
            "fallback_pattern": "I promise I will do my best to make things right and to earn back your trust.",
            "placeholder_labels": [],
        },
    ],
    "thanks_letter": [
        {
            "slot_key": "p3_feeling_1",
            "purpose": "表达感恩之情",
            "required_points": ["情感表达"],
            "fallback_pattern": "I feel deeply grateful for your kindness, and your help has meant a great deal to me.",
            "placeholder_labels": [],
        },
        {
            "slot_key": "p3_reflection_1",
            "purpose": "表达感悟或回报之心",
            "required_points": ["个人感悟"],
            "fallback_pattern": "This experience has taught me to treasure kindness, and I hope to pass it on to others.",
            "placeholder_labels": [],
        },
    ],
    "default": [
        {
            "slot_key": "p3_feeling_1",
            "purpose": "表达个人感受",
            "required_points": ["情感表达"],
            "fallback_pattern": "I felt truly inspired by this experience, and it left a deep impression on me.",
            "placeholder_labels": [],
        },
        {
            "slot_key": "p3_reflection_1",
            "purpose": "表达感悟或启示",
            "required_points": ["个人感悟"],
            "fallback_pattern": "Looking back, I realize this has shaped who I am and how I see the world.",
            "placeholder_labels": [],
        },
    ],
}


# ============================================================
# 差异化 transition_words
# ============================================================

TRANSITION_WORDS_POOL = {
    "reply_letter": ["First of all,", "Additionally,", "More importantly,", "In the end,"],
    "invite_letter": ["To begin with,", "Furthermore,", "Most importantly,", "Finally,"],
    "suggestion_letter": ["First of all,", "In addition,", "Above all,", "To sum up,"],
    "intro_letter": ["For a start,", "Besides,", "Above all,", "Last but not least,"],
    "apology_letter": ["First and foremost,", "What is more,", "Most importantly,", "In conclusion,"],
    "thanks_letter": ["To begin with,", "Additionally,", "Most importantly,", "All in all,"],
    "campus_activity": ["At first,", "Before long,", "Soon afterward,", "Eventually,"],
    "memorable_experience": ["At the beginning,", "During the process,", "To my surprise,", "In the end,"],
    "dream_goal": ["When I first", "Over time,", "Step by step,", "Finally,"],
    "growth": ["In the beginning,", "As time went on,", "It was then that I realized,", "Now I understand,"],
    "volunteer": ["At first,", "During the activity,", "What moved me most was,", "Afterward,"],
    "culture": ["Initially,", "During the experience,", "I was amazed to find,", "From this,"],
    "labor": ["At the start,", "While working,", "I felt a sense of,", "Eventually,"],
    "friendship": ["At first,", "Through shared efforts,", "That was when I understood,", "From then on,"],
    "hobby": ["Originally,", "As I kept practicing,", "It suddenly struck me that,", "From then on,"],
    "teacher": ["When we first met,", "During our conversations,", "What impressed me most was,", "From that day,"],
    "competition": ["At the beginning,", "Despite the difficulty,", "When the moment came,", "In the final analysis,"],
    "family": ["Looking back,", "When I reflect on it,", "That experience taught me,", "Now I cherish,"],
    "travel": ["When I arrived,", "Before I knew it,", "I was overwhelmed by,", "Back home,"],
    "dream": ["Since childhood,", "As I grew older,", "It hit me that,", "Therefore,"],
    "perseverance": ["At first,", "Just when I felt like giving up,", "It was then that I discovered,", "Now I know,"],
    "challenge": ["Initially,", "Midway through,", "The turning point came when,", "Finally,"],
    "opinion": ["In my opinion,", "Furthermore,", "On the other hand,", "To conclude,"],
    "default": ["First of all,", "In addition,", "Most importantly,", "To conclude,"],
}


# ============================================================
# 差异化 advanced_vocabulary
# ============================================================

ADVANCED_VOCABULARY_POOL = {
    "reply_letter": [
        {"word": "meaningful", "basic": "good", "usage": "描述活动或经历有意义"},
        {"word": "insightful", "basic": "useful", "usage": "描述内容有启发性"},
        {"word": "thrilled", "basic": "happy", "usage": "描述兴奋心情"},
    ],
    "invite_letter": [
        {"word": "delighted", "basic": "happy", "usage": "表达愉快"},
        {"word": "honoured", "basic": "proud", "usage": "表达荣幸"},
        {"word": "memorable", "basic": "unforgettable", "usage": "描述难忘经历"},
    ],
    "suggestion_letter": [
        {"word": "beneficial", "basic": "good", "usage": "描述益处"},
        {"word": "constructive", "basic": "helpful", "usage": "描述建议有建设性"},
        {"word": "valuable", "basic": "useful", "usage": "描述建议有价值"},
    ],
    "intro_letter": [
        {"word": "fascinating", "basic": "interesting", "usage": "描述引人入胜的事物"},
        {"word": "remarkable", "basic": "great", "usage": "描述出众的特点"},
        {"word": "outstanding", "basic": "excellent", "usage": "描述杰出的事物"},
    ],
    "apology_letter": [
        {"word": "sincere", "basic": "real", "usage": "表达真诚歉意"},
        {"word": "genuinely", "basic": "really", "usage": "强调真实感受"},
        {"word": "remorseful", "basic": "sorry", "usage": "表达悔意"},
    ],
    "thanks_letter": [
        {"word": "grateful", "basic": "thankful", "usage": "表达感激"},
        {"word": "appreciate", "basic": "like", "usage": "描述欣赏"},
        {"word": "cherish", "basic": "value", "usage": "描述珍惜"},
    ],
    "default": [
        {"word": "meaningful", "basic": "good", "usage": "描述活动或经历有意义"},
        {"word": "memorable", "basic": "unforgettable", "usage": "描述经历难忘"},
        {"word": "insightful", "basic": "useful", "usage": "描述有启发性"},
    ],
}


# ============================================================
# 差异化 tips
# ============================================================

TIPS_POOL = {
    "reply_letter": "紧扣来信问题逐条作答；加入个人感受和体会，让回信更有温度；注意自然过渡，避免条目式罗列。",
    "invite_letter": "清晰说明活动内容、时间、地点；表达对邀请对象的尊重和期待；结尾礼貌询问回复。",
    "suggestion_letter": "建议要具体可行，理由要充分；适当表达对对方的关心；结尾表达期待采纳的愿望。",
    "intro_letter": "介绍内容要条理清晰，详略得当；加入个人情感，让介绍更生动；注意开头吸引读者兴趣。",
    "apology_letter": "道歉要真诚，不找借口；解释原因简洁明了；提出弥补措施；表达挽回关系的诚意。",
    "thanks_letter": "感谢要具体说出感谢的原因；表达真情实感；可提及对方行为对你的影响和启发。",
    "default": "紧扣题目要求，叙事清晰；加入个人感受和思考；注意语言自然、情感真挚。",
}


def get_template_type(template_key: str, template_name: str) -> str:
    """根据 template_key 或 template_name 判断模板类型"""
    key_lower = (template_key or "").lower()
    name_lower = (template_name or "").lower()

    for keyword, type_name in [
        ("reply", "reply_letter"),
        ("invite", "invite_letter"),
        ("suggestion", "suggestion_letter"),
        ("intro", "intro_letter"),
        ("apology", "apology_letter"),
        ("thanks", "thanks_letter"),
        ("activity", "campus_activity"),
        ("memorable", "memorable_experience"),
        ("dream", "dream_goal"),
        ("volunteer", "volunteer"),
        ("culture", "culture"),
        ("opinion", "opinion"),
        ("growth", "growth"),
        ("labor", "labor"),
        ("friendship", "friendship"),
        ("hobby", "hobby"),
        ("teacher", "teacher"),
        ("competition", "competition"),
        ("family", "family"),
        ("travel", "travel"),
        ("challenge", "challenge"),
    ]:
        if keyword in key_lower or keyword in name_lower:
            return type_name
    return "default"


def _is_signoff_paragraph(para: dict) -> bool:
    """检测段落是否是署名/结束语段落"""
    first_slot_text = str(para.get("slots", [{}])[0].get("fallback_pattern", "")).lower() if para.get("slots") else ""
    purpose = str(para.get("purpose", "")).lower()
    signoff_keywords = ["best wishes", "yours sincerely", "truly yours", "li hua", "署名", "结束语", "签名"]
    return any(kw in first_slot_text or kw in purpose for kw in signoff_keywords)


def _schema_has_feeling_slots(schema: dict) -> bool:
    """检测 schema 是否已经添加过 feeling/reflection 槽位（幂等检查）"""
    marker_phrases = [
        "I was really excited about this, because it gave me a chance",
        "I have been looking forward to this event",
        "I genuinely care about this topic",
        "I feel truly sorry about what happened",
        "I feel deeply grateful for your kindness",
        "I felt truly inspired by this experience",
        "Looking back, I realize this experience taught me",
        "Sharing this brings me great joy",
        "I promise I will do my best to make things right",
        "This experience has taught me to treasure kindness",
    ]
    schema_str = json.dumps(schema, ensure_ascii=False)
    return any(phrase in schema_str for phrase in marker_phrases)


def add_feeling_slots_to_schema(schema: dict, template_type: str) -> dict:
    """给 template_schema_json 添加 feeling/reflection 槽位（幂等：只添加一次）"""
    if _schema_has_feeling_slots(schema):
        return schema

    feeling_slots = FEELING_SLOTS_BY_TYPE.get(template_type, FEELING_SLOTS_BY_TYPE["default"])
    paragraphs = schema.get("paragraphs", [])

    if not paragraphs:
        return schema

    # 找最后一个非署名段落
    last_content_idx = -1
    for i in range(len(paragraphs) - 1, -1, -1):
        if not _is_signoff_paragraph(paragraphs[i]):
            last_content_idx = i
            break

    # 找倒数第二段非署名段落
    second_last_idx = -1
    for i in range(len(paragraphs) - 1, -1, -1):
        if i != last_content_idx and not _is_signoff_paragraph(paragraphs[i]):
            second_last_idx = i
            break

    if last_content_idx >= 0:
        last_para = paragraphs[last_content_idx]
        new_slot_key = f"p{last_para['paragraph']}_s{len(last_para.get('slots', [])) + 1}"
        last_para["slots"].append({
            "slot_key": new_slot_key,
            "purpose": feeling_slots[0]["purpose"],
            "required_points": feeling_slots[0]["required_points"],
            "fallback_pattern": feeling_slots[0]["fallback_pattern"],
            "placeholder_labels": feeling_slots[0]["placeholder_labels"],
        })

    if second_last_idx >= 0:
        ref_para = paragraphs[second_last_idx]
        new_slot_key = f"p{ref_para['paragraph']}_s{len(ref_para.get('slots', [])) + 1}"
        ref_para["slots"].append({
            "slot_key": new_slot_key,
            "purpose": feeling_slots[1]["purpose"],
            "required_points": feeling_slots[1]["required_points"],
            "fallback_pattern": feeling_slots[1]["fallback_pattern"],
            "placeholder_labels": feeling_slots[1]["placeholder_labels"],
        })

    return schema


def build_template_content_from_schema(schema: dict) -> str:
    """根据 schema 重建 flat template_content 文本（跳过署名段落）"""
    paragraphs = schema.get("paragraphs", [])
    lines = []
    for para in paragraphs:
        first_slot = (para.get("slots", []) or [{}])[0].get("fallback_pattern", "")
        if any(kw in first_slot.lower() for kw in ["best wishes", "yours sincerely", "li hua"]):
            continue
        for slot in para.get("slots", []):
            lines.append(slot.get("fallback_pattern", ""))
    return "\n".join(lines)


def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 读取所有模板
    cursor.execute("""
        SELECT id, template_name, template_key, template_content,
               template_schema_json, transition_words, advanced_vocabulary,
               tips, grammar_points, template_version
        FROM writing_templates
        ORDER BY id
    """)
    rows = cursor.fetchall()

    print(f"找到 {len(rows)} 个模板，开始升级...")

    updated = 0
    skipped = 0

    for row in rows:
        (tid, tname, tkey, tcontent, tschema_json,
         ttrans, tvocab, ttips, tgrammar, tver) = row

        template_type = get_template_type(tkey or "", tname or "")

        # 1. 解析并更新 schema
        try:
            schema = json.loads(tschema_json) if tschema_json else {}
        except Exception:
            schema = {}

        if schema:
            schema = add_feeling_slots_to_schema(schema, template_type)
        else:
            # 无 schema 的情况，跳过
            skipped += 1
            continue

        new_schema_json = json.dumps(schema, ensure_ascii=False)
        new_content = build_template_content_from_schema(schema)

        # 2. 更新 transition_words（差异化）
        trans_key = template_type if template_type in TRANSITION_WORDS_POOL else "default"
        new_transition_words = json.dumps(
            TRANSITION_WORDS_POOL.get(trans_key, TRANSITION_WORDS_POOL["default"]),
            ensure_ascii=False
        )

        # 3. 更新 advanced_vocabulary（差异化 + 丰富化）
        vocab_key = template_type if template_type in ADVANCED_VOCABULARY_POOL else "default"
        new_vocab = json.dumps(
            ADVANCED_VOCABULARY_POOL.get(vocab_key, ADVANCED_VOCABULARY_POOL["default"]),
            ensure_ascii=False
        )

        # 4. 更新 tips
        tips_key = template_type if template_type in TIPS_POOL else "default"
        new_tips = TIPS_POOL.get(tips_key, TIPS_POOL["default"])

        # 5. 更新 grammar_points（更具体）
        new_grammar = json.dumps([
            "注意时态统一，根据场景选择一般过去时（叙述经历）或一般现在时（说明介绍）。",
            "尝试在叙述中使用定语从句（who/which/where）丰富细节。",
            "在表达感悟时使用 It taught me that... / This experience made me realize... 等句型。",
            "使用恰当的过渡词使文章衔接自然。",
        ], ensure_ascii=False)

        # 6. Bump version
        new_version = (tver or 1) + 1

        # UPDATE 语句 - 字段顺序与 SELECT 完全对应
        cursor.execute("""
            UPDATE writing_templates SET
                template_schema_json = ?,
                template_content = ?,
                transition_words = ?,
                advanced_vocabulary = ?,
                tips = ?,
                grammar_points = ?,
                template_version = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            new_schema_json,    # template_schema_json
            new_content,         # template_content
            new_transition_words, # transition_words
            new_vocab,           # advanced_vocabulary
            new_tips,            # tips
            new_grammar,        # grammar_points
            new_version,         # template_version
            datetime.now().isoformat(),  # updated_at
            tid,                 # WHERE id = ?
        ))

        updated += 1
        print(f"  [✓] 模板 {tid}: {tname} (type={template_type}, ver {tver}→{new_version})")

    conn.commit()

    # 验证：抽查模板 6
    cursor.execute("""
        SELECT id, template_version, template_content, template_schema_json
        FROM writing_templates WHERE id = 6
    """)
    r = cursor.fetchone()
    print(f"\n验证模板6: ver={r[1]}")
    if r[3]:
        schema_check = json.loads(r[3])
        for p in schema_check.get("paragraphs", []):
            pnum = p["paragraph"]
            for s in p.get("slots", []):
                fp = s.get("fallback_pattern", "")
                if len(fp) > 50:
                    print(f"  Para{pnum} {s['slot_key']}: {fp[:60]}...")
    print(f"\n完成！共更新 {updated} 个模板，跳过 {skipped} 个。")
    print("下一步请运行：cd backend && python scripts/rebuild_writing_official_assets.py --skip-template-refresh")

    conn.close()


if __name__ == "__main__":
    main()
