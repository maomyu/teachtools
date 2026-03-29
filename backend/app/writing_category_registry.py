"""
作文分类注册表

[INPUT]: 提供数据库预置的作文分类树定义
[OUTPUT]: 对外提供分类种子数据与辅助函数
[POS]: backend/app 的作文分类注册表
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List


WRITING_CATEGORY_TREE: List[Dict[str, Any]] = [
    {
        "code": "application",
        "name": "应用文",
        "template_key": "group.application",
        "prompt_hint": "北京中考英语应用文写作，强调格式、目的明确、礼貌表达和实用场景。",
        "keywords": ["dear", "email", "letter", "write to", "邀请", "建议", "申请", "通知", "发言"],
        "children": [
            {
                "code": "application.invitation",
                "name": "邀请沟通类",
                "template_key": "major.application.invitation",
                "prompt_hint": "围绕邀请、回复邀请、活动沟通展开，重点写清活动信息、期待回复与礼貌表达。",
                "keywords": ["invite", "invitation", "attend", "join", "参加", "邀请"],
                "children": [
                    {
                        "code": "application.invitation.invitation_letter",
                        "name": "邀请信",
                        "template_key": "invite_letter",
                        "prompt_hint": "邀请对方参加活动，写清活动时间、地点、内容、意义和期待回复。",
                        "keywords": ["invite you", "would like to invite", "邀请你", "参加活动"],
                    },
                    {
                        "code": "application.invitation.reply_letter",
                        "name": "邀请回复信",
                        "template_key": "invite_reply",
                        "prompt_hint": "对邀请进行接受或婉拒回复，说明原因并保持礼貌。",
                        "keywords": ["thanks for your invitation", "can't attend", "accept", "refuse", "回复邀请"],
                    },
                    {
                        "code": "application.invitation.activity_email",
                        "name": "活动邀请邮件",
                        "template_key": "activity_invite_email",
                        "prompt_hint": "通过邮件邀请他人参加校园或社会活动，兼顾活动介绍和邀请语气。",
                        "keywords": ["email", "activity", "join us", "邮件邀请", "活动邮件"],
                    },
                ],
            },
            {
                "code": "application.advice",
                "name": "建议求助类",
                "template_key": "major.application.advice",
                "prompt_hint": "围绕提出建议、回应烦恼、解决问题展开，重点是问题分析与分点建议。",
                "keywords": ["suggest", "advice", "problem", "help", "求助", "建议"],
                "children": [
                    {
                        "code": "application.advice.suggestion_letter",
                        "name": "建议信",
                        "template_key": "suggestion_letter",
                        "prompt_hint": "针对某个问题提出2到3点建议，说明理由和预期效果。",
                        "keywords": ["suggestions", "advice on", "建议", "提建议"],
                    },
                    {
                        "code": "application.advice.help_letter",
                        "name": "求助信",
                        "template_key": "help_letter",
                        "prompt_hint": "写信向他人求助，说明当前困难、求助事项和感谢。",
                        "keywords": ["need your help", "ask for help", "求助", "帮助我"],
                    },
                    {
                        "code": "application.advice.problem_solution",
                        "name": "问题解决建议",
                        "template_key": "problem_solution",
                        "prompt_hint": "围绕具体问题提出解决方案，适合校园生活、学习困扰、习惯养成类题目。",
                        "keywords": ["solve", "problem", "solution", "如何解决", "解决问题"],
                    },
                ],
            },
            {
                "code": "application.introduction",
                "name": "介绍说明类",
                "template_key": "major.application.introduction",
                "prompt_hint": "围绕人物、学校、活动或事物介绍展开，重点是信息完整和表达清晰。",
                "keywords": ["introduce", "introduction", "介绍", "recommend", "介绍一下"],
                "children": [
                    {
                        "code": "application.introduction.intro_letter",
                        "name": "介绍信",
                        "template_key": "intro_letter",
                        "prompt_hint": "向对方介绍人物、地点、活动或中国文化内容，结构清楚、信息完整。",
                        "keywords": ["introduce", "let me introduce", "介绍信", "向你介绍"],
                    },
                    {
                        "code": "application.introduction.person_intro",
                        "name": "人物介绍",
                        "template_key": "person_intro",
                        "prompt_hint": "介绍人物身份、特点、经历与影响，适合推荐人物或榜样类题目。",
                        "keywords": ["person", "people", "人物", "榜样", "介绍某人"],
                    },
                    {
                        "code": "application.introduction.activity_intro",
                        "name": "活动介绍",
                        "template_key": "activity_intro",
                        "prompt_hint": "介绍校园活动、社团活动、节日活动安排与亮点。",
                        "keywords": ["activity", "club", "festival", "活动介绍", "社团"],
                    },
                ],
            },
            {
                "code": "application.thanks_apology",
                "name": "感谢道歉类",
                "template_key": "major.application.thanks_apology",
                "prompt_hint": "强调情感表达和礼貌语气，说明原因并体现真诚态度。",
                "keywords": ["thank", "grateful", "sorry", "apologize", "感谢", "道歉"],
                "children": [
                    {
                        "code": "application.thanks_apology.thanks_letter",
                        "name": "感谢信",
                        "template_key": "thanks_letter",
                        "prompt_hint": "表达感谢，说明对方帮助带来的具体影响和感受。",
                        "keywords": ["thank you", "grateful", "感谢信", "感谢你"],
                    },
                    {
                        "code": "application.thanks_apology.apology_letter",
                        "name": "道歉信",
                        "template_key": "apology_letter",
                        "prompt_hint": "说明道歉原因、补救措施和未来承诺，语气真诚。",
                        "keywords": ["apologize", "sorry for", "道歉信", "抱歉"],
                    },
                ],
            },
            {
                "code": "application.application",
                "name": "申请自荐类",
                "template_key": "major.application.application",
                "prompt_hint": "强调申请目的、自身优势、匹配理由和期待回复。",
                "keywords": ["apply", "application", "volunteer", "join", "申请", "自荐", "竞选"],
                "children": [
                    {
                        "code": "application.application.application_letter",
                        "name": "申请信",
                        "template_key": "application_letter",
                        "prompt_hint": "申请职位、活动机会或项目资格，写清个人条件和申请原因。",
                        "keywords": ["apply for", "application letter", "申请参加", "申请加入"],
                    },
                    {
                        "code": "application.application.self_recommendation",
                        "name": "自荐信",
                        "template_key": "self_recommendation",
                        "prompt_hint": "向他人推荐自己，突出能力、经验和匹配度。",
                        "keywords": ["recommend myself", "自荐", "推荐自己", "suitable for"],
                    },
                    {
                        "code": "application.application.campaign_speech",
                        "name": "竞选稿",
                        "template_key": "campaign_speech",
                        "prompt_hint": "用于竞选班干部、社团职位等，突出优势、计划与号召力。",
                        "keywords": ["campaign", "monitor", "president", "竞选", "班干部"],
                    },
                ],
            },
            {
                "code": "application.notice",
                "name": "通知倡议类",
                "template_key": "major.application.notice",
                "prompt_hint": "强调对象、事项、时间地点和行动号召，语言简洁清晰。",
                "keywords": ["notice", "announcement", "speech", "倡议", "通知", "发言"],
                "children": [
                    {
                        "code": "application.notice.notice",
                        "name": "通知",
                        "template_key": "notice",
                        "prompt_hint": "发布活动或安排通知，写清时间、地点、对象和注意事项。",
                        "keywords": ["notice", "通知", "announce"],
                    },
                    {
                        "code": "application.notice.proposal",
                        "name": "倡议书",
                        "template_key": "proposal",
                        "prompt_hint": "围绕文明、环保、公益等提出号召与建议，强调行动呼吁。",
                        "keywords": ["call on", "倡议", "proposal", "共同做"],
                    },
                    {
                        "code": "application.notice.speech",
                        "name": "演讲稿",
                        "template_key": "speech",
                        "prompt_hint": "用于演讲或发言，重视称呼、观点展开和结尾号召。",
                        "keywords": ["speech", "ladies and gentlemen", "演讲稿", "发言稿"],
                    },
                ],
            },
            {
                "code": "application.plan",
                "name": "活动安排类",
                "template_key": "major.application.plan",
                "prompt_hint": "围绕活动策划、行程安排和方案设计，重视流程与分工。",
                "keywords": ["plan", "schedule", "arrangement", "安排", "计划"],
                "children": [
                    {
                        "code": "application.plan.activity_plan",
                        "name": "活动计划",
                        "template_key": "activity_plan",
                        "prompt_hint": "围绕校园、社团、班级活动提出时间安排、内容和目标。",
                        "keywords": ["activity plan", "活动计划", "安排活动"],
                    },
                    {
                        "code": "application.plan.schedule",
                        "name": "行程安排",
                        "template_key": "schedule",
                        "prompt_hint": "介绍一天或几天的安排，突出时间顺序和活动内容。",
                        "keywords": ["schedule", "trip", "行程", "日程安排"],
                    },
                    {
                        "code": "application.plan.club_scheme",
                        "name": "社团方案",
                        "template_key": "club_scheme",
                        "prompt_hint": "围绕社团、班级项目或校园改进提出实施方案。",
                        "keywords": ["club", "scheme", "社团", "方案"],
                    },
                ],
            },
            {
                "code": "application.feedback",
                "name": "回复反馈类",
                "template_key": "major.application.feedback",
                "prompt_hint": "围绕回信、反馈意见、说明结果等情境，强调回应性和针对性。",
                "keywords": ["reply", "feedback", "respond", "回信", "反馈"],
                "children": [
                    {
                        "code": "application.feedback.reply_letter",
                        "name": "回信",
                        "template_key": "reply_letter",
                        "prompt_hint": "根据来信问题逐项回应，表达态度、建议或邀请。",
                        "keywords": ["reply", "letter", "回信", "收到你的来信"],
                    },
                    {
                        "code": "application.feedback.feedback_report",
                        "name": "意见反馈",
                        "template_key": "feedback_report",
                        "prompt_hint": "对活动、课程、设施等给出反馈意见和改进建议。",
                        "keywords": ["feedback", "opinion", "意见反馈", "看法建议"],
                    },
                    {
                        "code": "application.feedback.result_explanation",
                        "name": "结果说明",
                        "template_key": "result_explanation",
                        "prompt_hint": "说明决定、结果或变化，兼顾原因解释与后续安排。",
                        "keywords": ["result", "explain", "通知结果", "说明情况"],
                    },
                ],
            },
        ],
    },
    {
        "code": "narrative",
        "name": "记叙文",
        "template_key": "group.narrative",
        "prompt_hint": "北京中考英语记叙类写作，强调经历、细节、情感变化和主题感悟。",
        "keywords": ["experience", "story", "remember", "经历", "故事", "难忘"],
        "children": [
            {
                "code": "narrative.growth",
                "name": "成长励志类",
                "template_key": "major.narrative.growth",
                "prompt_hint": "围绕坚持、突破、梦想、成长目标展开，突出转变与收获。",
                "keywords": ["坚持", "努力", "dream", "goal", "success", "挫折", "成长"],
                "children": [
                    {
                        "code": "narrative.growth.persistence",
                        "name": "坚持成长",
                        "template_key": "persistence_growth",
                        "prompt_hint": "通过一段坚持过程体现成长与突破，适合训练努力、克服困难类题目。",
                        "keywords": ["坚持", "keep", "never give up", "困难", "练习"],
                    },
                    {
                        "code": "narrative.growth.breakthrough",
                        "name": "挫折突破",
                        "template_key": "breakthrough",
                        "prompt_hint": "讲述遭遇挫折后重整心态并最终突破的经历。",
                        "keywords": ["挫折", "failed", "difficulty", "overcome", "突破"],
                    },
                    {
                        "code": "narrative.growth.dream_goal",
                        "name": "梦想目标",
                        "template_key": "dream_goal",
                        "prompt_hint": "围绕梦想、目标、未来计划写作，强调原因与行动。",
                        "keywords": ["dream", "future", "goal", "理想", "目标"],
                    },
                ],
            },
            {
                "code": "narrative.relationship",
                "name": "人际情感类",
                "template_key": "major.narrative.relationship",
                "prompt_hint": "围绕亲情、友情、师生关系与他人帮助展开，突出情感变化。",
                "keywords": ["family", "friend", "teacher", "help", "亲情", "友情", "老师"],
                "children": [
                    {
                        "code": "narrative.relationship.family",
                        "name": "亲情关爱",
                        "template_key": "family_care",
                        "prompt_hint": "记录家庭成员之间的关爱、理解与成长。",
                        "keywords": ["mother", "father", "family", "家人", "亲情"],
                    },
                    {
                        "code": "narrative.relationship.friendship",
                        "name": "友情合作",
                        "template_key": "friendship_teamwork",
                        "prompt_hint": "讲述朋友之间互助、合作、误会化解或共同成长。",
                        "keywords": ["friend", "friendship", "teamwork", "朋友", "合作"],
                    },
                    {
                        "code": "narrative.relationship.teacher",
                        "name": "师生互动",
                        "template_key": "teacher_student",
                        "prompt_hint": "围绕老师的帮助、鼓励或一次印象深刻的师生互动展开。",
                        "keywords": ["teacher", "class", "老师", "鼓励"],
                    },
                ],
            },
            {
                "code": "narrative.campus",
                "name": "校园经历类",
                "template_key": "major.narrative.campus",
                "prompt_hint": "围绕校园活动、课堂体验、社团和比赛经历展开。",
                "keywords": ["school", "campus", "class", "club", "competition", "校园", "比赛"],
                "children": [
                    {
                        "code": "narrative.campus.activity",
                        "name": "校园活动",
                        "template_key": "campus_activity",
                        "prompt_hint": "记录运动会、艺术节、科技节等校园活动中的所见所感。",
                        "keywords": ["school activity", "sports meeting", "校园活动", "艺术节"],
                    },
                    {
                        "code": "narrative.campus.classroom",
                        "name": "课堂经历",
                        "template_key": "classroom_experience",
                        "prompt_hint": "讲述课堂上的一次特别经历或学习体验。",
                        "keywords": ["classroom", "lesson", "课堂", "上课"],
                    },
                    {
                        "code": "narrative.campus.competition",
                        "name": "比赛经历",
                        "template_key": "competition_experience",
                        "prompt_hint": "记录比赛、演讲、展示等经历中的挑战与收获。",
                        "keywords": ["competition", "contest", "比赛", "演讲比赛"],
                    },
                ],
            },
            {
                "code": "narrative.practice",
                "name": "社会实践类",
                "template_key": "major.narrative.practice",
                "prompt_hint": "围绕志愿服务、劳动实践、社会观察等真实经历展开。",
                "keywords": ["volunteer", "service", "labor", "community", "志愿", "劳动"],
                "children": [
                    {
                        "code": "narrative.practice.volunteer",
                        "name": "志愿服务",
                        "template_key": "volunteer_service",
                        "prompt_hint": "描述一次志愿服务经历，强调帮助他人与自我收获。",
                        "keywords": ["volunteer", "service", "志愿服务"],
                    },
                    {
                        "code": "narrative.practice.labor",
                        "name": "劳动实践",
                        "template_key": "labor_practice",
                        "prompt_hint": "记录劳动、家务、种植等实践活动，突出责任感与体验。",
                        "keywords": ["labor", "housework", "劳动", "实践"],
                    },
                    {
                        "code": "narrative.practice.observation",
                        "name": "社会观察",
                        "template_key": "social_observation",
                        "prompt_hint": "通过一次社会观察、采访、参观引出认识与思考。",
                        "keywords": ["visit", "observe", "参观", "采访", "社会观察"],
                    },
                ],
            },
            {
                "code": "narrative.culture",
                "name": "文化体验类",
                "template_key": "major.narrative.culture",
                "prompt_hint": "围绕传统文化、节日活动、文化交流体验展开。",
                "keywords": ["traditional", "festival", "culture", "传统文化", "节日"],
                "children": [
                    {
                        "code": "narrative.culture.traditional_culture",
                        "name": "传统文化",
                        "template_key": "traditional_culture",
                        "prompt_hint": "记录接触中国传统文化的体验与感受，如书法、戏曲、非遗等。",
                        "keywords": ["traditional culture", "书法", "京剧", "非遗", "传统文化"],
                    },
                    {
                        "code": "narrative.culture.festival_custom",
                        "name": "节日习俗",
                        "template_key": "festival_custom",
                        "prompt_hint": "围绕节日活动、习俗体验或节日意义展开。",
                        "keywords": ["festival", "Spring Festival", "Mid-Autumn", "节日习俗"],
                    },
                    {
                        "code": "narrative.culture.cultural_exchange",
                        "name": "文化传播",
                        "template_key": "cultural_exchange",
                        "prompt_hint": "围绕向外国朋友介绍中国文化、跨文化体验或交流展开。",
                        "keywords": ["foreign friend", "exchange", "introduce Chinese culture", "文化交流"],
                    },
                ],
            },
            {
                "code": "narrative.life",
                "name": "生活感悟类",
                "template_key": "major.narrative.life",
                "prompt_hint": "围绕生活中的难忘经历、旅行见闻和小事感悟展开。",
                "keywords": ["life", "experience", "trip", "travel", "难忘", "生活"],
                "children": [
                    {
                        "code": "narrative.life.memorable",
                        "name": "难忘经历",
                        "template_key": "memorable_experience",
                        "prompt_hint": "叙述一次难忘经历，并总结自己的收获。",
                        "keywords": ["memorable", "unforgettable", "难忘经历"],
                    },
                    {
                        "code": "narrative.life.travel",
                        "name": "旅行见闻",
                        "template_key": "travel_experience",
                        "prompt_hint": "描述一次旅行中的所见所闻与感受。",
                        "keywords": ["travel", "trip", "旅行", "参观"],
                    },
                    {
                        "code": "narrative.life.daily_insight",
                        "name": "日常感悟",
                        "template_key": "daily_insight",
                        "prompt_hint": "从一件日常小事中获得启发，强调细节与感悟。",
                        "keywords": ["daily life", "small thing", "日常", "感悟"],
                    },
                ],
            },
            {
                "code": "narrative.interest_tech",
                "name": "兴趣科技类",
                "template_key": "major.narrative.interest_tech",
                "prompt_hint": "围绕兴趣培养、科技体验、网络生活展开。",
                "keywords": ["hobby", "interest", "technology", "AI", "网络", "科技"],
                "children": [
                    {
                        "code": "narrative.interest_tech.hobby",
                        "name": "兴趣培养",
                        "template_key": "hobby_growth",
                        "prompt_hint": "描述自己培养兴趣爱好的一段经历以及成长。",
                        "keywords": ["hobby", "interest", "兴趣爱好"],
                    },
                    {
                        "code": "narrative.interest_tech.tech_experience",
                        "name": "科技体验",
                        "template_key": "tech_experience",
                        "prompt_hint": "记录一次科技活动、科技产品使用或科技学习体验。",
                        "keywords": ["technology", "robot", "AI", "科技体验"],
                    },
                    {
                        "code": "narrative.interest_tech.online_life",
                        "name": "网络生活",
                        "template_key": "online_life",
                        "prompt_hint": "围绕网络学习、手机使用、线上沟通等生活体验展开。",
                        "keywords": ["internet", "online", "phone", "网络生活"],
                    },
                ],
            },
            {
                "code": "narrative.public_good",
                "name": "环保公益类",
                "template_key": "major.narrative.public_good",
                "prompt_hint": "围绕环保行动、文明行为和公益参与展开。",
                "keywords": ["environment", "protect", "green", "volunteer", "环保", "公益"],
                "children": [
                    {
                        "code": "narrative.public_good.environment",
                        "name": "环保行动",
                        "template_key": "environment_action",
                        "prompt_hint": "讲述一次环保行动或绿色生活实践，突出影响与感悟。",
                        "keywords": ["protect the environment", "环保", "低碳", "垃圾分类"],
                    },
                    {
                        "code": "narrative.public_good.civilized_behavior",
                        "name": "文明行为",
                        "template_key": "civilized_behavior",
                        "prompt_hint": "围绕文明礼仪、公共行为和社会责任展开。",
                        "keywords": ["civilized", "manners", "文明行为", "礼貌"],
                    },
                    {
                        "code": "narrative.public_good.public_service",
                        "name": "公益参与",
                        "template_key": "public_service",
                        "prompt_hint": "记录参与公益活动、帮助他人或服务社会的经历。",
                        "keywords": ["charity", "public service", "公益", "帮助他人"],
                    },
                ],
            },
        ],
    },
    {
        "code": "expression",
        "name": "表达拓展类",
        "template_key": "group.expression",
        "prompt_hint": "北京中考英语观点表达与说明分析类写作，强调观点、条理和说明性表达。",
        "keywords": ["opinion", "view", "rule", "how to", "观点", "说明", "方法"],
        "children": [
            {
                "code": "expression.opinion",
                "name": "观点表达类",
                "template_key": "major.expression.opinion",
                "prompt_hint": "围绕个人观点、利弊分析和现象评价展开。",
                "keywords": ["opinion", "view", "think", "agree", "观点", "看法"],
                "children": [
                    {
                        "code": "expression.opinion.pro_con",
                        "name": "利弊分析",
                        "template_key": "pro_con_analysis",
                        "prompt_hint": "针对某个现象或做法分析优缺点，再给出个人结论。",
                        "keywords": ["advantages", "disadvantages", "利弊", "优缺点"],
                    },
                    {
                        "code": "expression.opinion.personal_view",
                        "name": "个人看法",
                        "template_key": "personal_view",
                        "prompt_hint": "围绕某一问题表达观点并给出理由，结构清晰、分点论述。",
                        "keywords": ["in my opinion", "I think", "个人看法", "你的观点"],
                    },
                    {
                        "code": "expression.opinion.issue_comment",
                        "name": "现象评价",
                        "template_key": "issue_comment",
                        "prompt_hint": "针对校园、社会或网络现象进行评价，兼顾问题与建议。",
                        "keywords": ["phenomenon", "social issue", "现象评价", "评价"],
                    },
                ],
            },
            {
                "code": "expression.exposition",
                "name": "说明分析类",
                "template_key": "major.expression.exposition",
                "prompt_hint": "围绕方法介绍、规则说明和流程分析展开，重在信息准确和步骤清晰。",
                "keywords": ["how to", "rule", "steps", "介绍方法", "说明"],
                "children": [
                    {
                        "code": "expression.exposition.method_intro",
                        "name": "方法介绍",
                        "template_key": "method_intro",
                        "prompt_hint": "介绍学习方法、生活技能或活动准备方法，适合步骤说明类题目。",
                        "keywords": ["how to", "method", "方法介绍", "建议做法"],
                    },
                    {
                        "code": "expression.exposition.rule_explain",
                        "name": "规则说明",
                        "template_key": "rule_explain",
                        "prompt_hint": "介绍学校规则、活动规则或行为规范，强调清楚易懂。",
                        "keywords": ["rules", "regulations", "规则说明", "校规"],
                    },
                    {
                        "code": "expression.exposition.process_explain",
                        "name": "流程说明",
                        "template_key": "process_explain",
                        "prompt_hint": "说明活动流程、制作流程或操作步骤，突出顺序性。",
                        "keywords": ["process", "steps", "流程", "步骤"],
                    },
                ],
            },
        ],
    },
]


def flatten_writing_categories() -> List[Dict[str, Any]]:
    """将树形分类展开为带父子信息的列表。"""
    rows: List[Dict[str, Any]] = []

    def walk(nodes: Iterable[Dict[str, Any]], level: int, parent_code: str | None, parent_path: List[str]) -> None:
        for index, node in enumerate(nodes, start=1):
            path_names = [*parent_path, node["name"]]
            rows.append(
                {
                    "code": node["code"],
                    "name": node["name"],
                    "level": level,
                    "parent_code": parent_code,
                    "path": " / ".join(path_names),
                    "template_key": node.get("template_key") or node["code"],
                    "prompt_hint": node.get("prompt_hint", ""),
                    "sort_order": index,
                    "is_active": True,
                    "keywords": node.get("keywords", []),
                }
            )
            children = node.get("children") or []
            if children:
                walk(children, level + 1, node["code"], path_names)

    walk(WRITING_CATEGORY_TREE, level=1, parent_code=None, parent_path=[])
    return rows


def leaf_category_rows() -> List[Dict[str, Any]]:
    """获取最底层子类。"""
    return [row for row in flatten_writing_categories() if row["level"] == 3]


def category_seed_map() -> Dict[str, Dict[str, Any]]:
    """按 code 建立索引。"""
    return {row["code"]: row for row in flatten_writing_categories()}
