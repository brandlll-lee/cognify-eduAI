"""
DSE英文阅读理解相关数据模型

本模块定义了DSE Demo系统所需的所有Pydantic数据模型，
包括题目、答案、批改结果等核心业务实体。

设计原则：
- 类型安全：使用Pydantic进行严格的数据验证
- 文档完善：每个模型都有详细的字段说明
- 扩展性好：支持未来功能扩展
- API友好：直接用于FastAPI的请求/响应模型
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from enum import Enum


class QuestionType(str, Enum):
    """题目类型枚举"""
    MULTIPLE_CHOICE = "multiple-choice"
    FILL_IN_BLANK = "fill-in-blank"
    TIMELINE_SEQUENCING = "timeline-sequencing"


class DemoStatus(str, Enum):
    """Demo状态枚举"""
    NOT_STARTED = "not-started"
    ANSWERING = "answering"
    REVIEWING = "reviewing"
    SUBMITTING = "submitting"
    GRADING = "grading"
    COMPLETED = "completed"
    VIEWING_RESULTS = "viewing-results"


class SkillType(str, Enum):
    """技能类型枚举"""
    VOCABULARY = "vocabulary"
    DETAIL = "detail"
    INFERENCE = "inference"
    MAIN_IDEA = "main-idea"
    STRUCTURE = "structure"
    SEQUENCING = "sequencing"


# ===== 基础数据模型 =====

class DSEPassage(BaseModel):
    """DSE阅读文章模型"""
    id: str = Field(..., description="文章唯一标识")
    title: str = Field(..., description="文章标题")
    content: str = Field(..., description="文章内容(HTML格式)")
    wordCount: int = Field(..., description="文章字数", alias="word_count")
    difficulty: Literal["Easy", "Medium", "Hard"] = Field(..., description="难度等级")
    year: int = Field(..., description="考试年份")
    paper: str = Field(..., description="试卷编号")

    class Config:
        populate_by_name = True  # 允许使用字段名或别名
        json_schema_extra = {
            "example": {
                "id": "dse-2023-flash-fiction",
                "title": "Flash Fiction: Writing a Story in 1,000 Words or Less",
                "content": "<p id='p1'>[1] People have been enjoying stories...</p>",
                "word_count": 847,
                "difficulty": "Medium",
                "year": 2023,
                "paper": "DSE-ENG LANG 1-A-RP-2"
            }
        }


class SubQuestion(BaseModel):
    """子题目模型(用于填空题)"""
    id: str = Field(..., description="子题目ID")
    questionText: str = Field(..., description="子题目文本", alias="question_text")
    correctAnswer: str = Field(..., description="正确答案", alias="correct_answer")
    marks: int = Field(..., description="分值")

    class Config:
        populate_by_name = True  # 允许使用字段名或别名
        json_schema_extra = {
            "example": {
                "id": "q5_i",
                "questionText": "(i) restrict",
                "correctAnswer": "limits",
                "marks": 1
            }
        }


class TimelineEvent(BaseModel):
    """时间线事件模型"""
    id: str = Field(..., description="事件ID")
    position: str = Field(..., description="位置标识(i/ii/iii/fixed)")
    description: str = Field(..., description="事件描述")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "event1",
                "position": "i",
                "description": "One month ago"
            }
        }


class TimelineOption(BaseModel):
    """时间线选项模型"""
    letter: str = Field(..., description="选项字母(A/B/C/D/E)")
    description: str = Field(..., description="选项描述")

    class Config:
        json_schema_extra = {
            "example": {
                "letter": "A",
                "description": "Timothy caused an explosion"
            }
        }


class DSEQuestion(BaseModel):
    """DSE题目模型"""
    id: str = Field(..., description="题目唯一标识")
    questionNumber: int = Field(..., description="题目编号", alias="question_number")
    questionText: str = Field(..., description="题目文本", alias="question_text")
    type: QuestionType = Field(..., description="题目类型")
    
    # 选择题相关
    options: Optional[List[str]] = Field(None, description="选择题选项")
    correctAnswer: Optional[str] = Field(None, description="选择题正确答案", alias="correct_answer")
    
    # 填空题相关
    subQuestions: Optional[List[SubQuestion]] = Field(None, description="填空题子题目", alias="sub_questions")
    
    # 时间线题相关
    timelineEvents: Optional[List[TimelineEvent]] = Field(None, description="时间线事件", alias="timeline_events")
    availableOptions: Optional[List[TimelineOption]] = Field(None, description="可选选项", alias="available_options")
    correctAnswers: Optional[Dict[str, str]] = Field(None, description="时间线正确答案映射", alias="correct_answers")
    
    totalMarks: int = Field(..., description="总分值", alias="total_marks")
    explanation: Optional[str] = Field(None, description="题目解析")
    skillType: SkillType = Field(..., description="考查技能类型", alias="skill_type")
    referenceParagraphs: Optional[List[str]] = Field(None, description="参考段落ID列表", alias="reference_paragraphs")

    class Config:
        populate_by_name = True  # 允许使用字段名或别名
        json_schema_extra = {
            "example": {
                "id": "q11",
                "question_number": 11,
                "question_text": "Which of the following is NOT mentioned...",
                "type": "multiple-choice",
                "options": ["A. ability to write more", "B. more efficient use of words"],
                "correct_answer": "A",
                "total_marks": 1,
                "skill_type": "detail",
                "reference_paragraphs": ["p10"]
            }
        }


# ===== 用户答案模型 =====

class UserAnswer(BaseModel):
    """用户答案模型"""
    question_id: str = Field(..., description="题目ID", alias="questionId")
    type: QuestionType = Field(..., description="题目类型")
    
    # 不同题型的答案
    selected_option: Optional[str] = Field(None, description="选择题选中选项", alias="selectedOption")
    fill_in_answers: Optional[Dict[str, str]] = Field(None, description="填空题答案映射", alias="fillInAnswers")
    timeline_answers: Optional[Dict[str, str]] = Field(None, description="时间线题答案映射", alias="timelineAnswers")

    class Config:
        populate_by_name = True  # 允许使用字段名或别名
        json_schema_extra = {
            "example": {
                "question_id": "q11",
                "type": "multiple-choice",
                "selected_option": "A"
            }
        }


# ===== 请求/响应模型 =====

class SubmitAnswersRequest(BaseModel):
    """提交答案请求模型"""
    answers: List[UserAnswer] = Field(..., description="用户答案列表")
    start_time: datetime = Field(..., description="开始答题时间", alias="startTime")
    end_time: datetime = Field(..., description="结束答题时间", alias="endTime")
    
    @validator('answers')
    def validate_answers_not_empty(cls, v):
        if not v:
            raise ValueError('答案列表不能为空')
        return v
    
    @validator('end_time')
    def validate_end_time_after_start(cls, v, values):
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('结束时间必须晚于开始时间')
        return v

    class Config:
        populate_by_name = True  # 允许使用字段名或别名
        json_schema_extra = {
            "example": {
                "answers": [
                    {
                        "question_id": "q11",
                        "type": "multiple-choice",
                        "selected_option": "A"
                    }
                ],
                "start_time": "2024-01-01T10:00:00Z",
                "end_time": "2024-01-01T10:30:00Z"
            }
        }


class SubmissionResponse(BaseModel):
    """提交响应模型"""
    submission_id: str = Field(..., description="提交ID")
    status: str = Field(..., description="提交状态")
    message: str = Field(..., description="响应消息")
    estimated_completion_time: int = Field(..., description="预计完成时间(秒)")

    class Config:
        json_schema_extra = {
            "example": {
                "submission_id": "submission_20240101_100001",
                "status": "processing",
                "message": "答案已提交，AI老师正在批改中...",
                "estimated_completion_time": 60
            }
        }


# ===== 批改结果模型 =====

class QuestionResult(BaseModel):
    """单题批改结果模型"""
    question_number: int = Field(..., alias="questionNumber", description="题目编号")
    is_correct: bool = Field(..., alias="isCorrect", description="是否正确")
    user_answer: str = Field(..., alias="userAnswer", description="用户答案")
    correct_answer: str = Field(..., alias="correctAnswer", description="正确答案")
    explanation: str = Field(..., description="详细解析")
    skill_analysis: str = Field(..., alias="skillAnalysis", description="技能分析")
    reference_text: Optional[str] = Field(None, alias="referenceText", description="原文引用")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "questionNumber": 11,
                "isCorrect": False,
                "userAnswer": "A",
                "correctAnswer": "A",
                "explanation": "这道题考查的是detail技能。根据第9段...",
                "skillAnalysis": "该题主要考查细节理解能力",
                "referenceText": "Flash fiction forces you to be economical..."
            }
        }


class SkillMastery(BaseModel):
    """技能掌握度模型"""
    skill_name: str = Field(..., alias="skillName", description="技能名稱")
    mastery_level: float = Field(..., alias="masteryLevel", description="掌握程度(0-1)")
    correct_count: int = Field(..., alias="correctCount", description="該技能答對題數")
    total_count: int = Field(..., alias="totalCount", description="該技能總題數")
    performance_description: str = Field(..., alias="performanceDescription", description="表現描述")
    
    class Config:
        populate_by_name = True

class StrengthDetail(BaseModel):
    """優勢能力詳細描述模型"""
    skill_name: str = Field(..., alias="skillName", description="技能名稱")
    mastery_level: float = Field(..., alias="masteryLevel", description="掌握程度(0-1)")
    description: str = Field(..., description="詳細描述")
    evidence: List[str] = Field(..., description="支撐證據")
    
    class Config:
        populate_by_name = True

class WeaknessDetail(BaseModel):
    """薄弱環節詳細描述模型"""
    skill_name: str = Field(..., alias="skillName", description="技能名稱")
    mastery_level: float = Field(..., alias="masteryLevel", description="掌握程度(0-1)")
    description: str = Field(..., description="問題描述")
    improvement_suggestions: List[str] = Field(..., alias="improvementSuggestions", description="改進建議")
    practice_focus: str = Field(..., alias="practiceFocus", description="練習重點")
    
    class Config:
        populate_by_name = True

class AITeacherResponse(BaseModel):
    """AI老师批改结果模型"""
    results: List[QuestionResult] = Field(..., description="各题批改结果")
    final_score: float = Field(..., alias="finalScore", description="最终得分(0-1)")
    correct_count: int = Field(..., alias="correctCount", description="正确题目数量")
    total_questions: int = Field(..., alias="totalQuestions", description="题目总数")
    ability_analysis: str = Field(..., alias="abilityAnalysis", description="能力分析")
    
    # 新增詳細能力分析數據
    skill_breakdown: List[SkillMastery] = Field(..., alias="skillBreakdown", description="技能掌握度分解")
    strengths_detailed: List[StrengthDetail] = Field(..., alias="strengthsDetailed", description="詳細優勢分析")
    weaknesses_detailed: List[WeaknessDetail] = Field(..., alias="weaknessesDetailed", description="詳細劣勢分析")
    
    # 保留原有字段以確保向後兼容
    strengths: List[str] = Field(..., description="优势技能列表")
    weaknesses: List[str] = Field(..., description="薄弱技能列表")
    recommendations: List[str] = Field(..., description="学习建议列表")
    time_spent: int = Field(..., alias="timeSpent", description="答题用时(秒)")

    @validator('final_score')
    def validate_score_range(cls, v):
        if not 0 <= v <= 1:
            raise ValueError('得分必须在0-1之间')
        return v

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "results": [],
                "finalScore": 0.67,
                "correctCount": 2,
                "totalQuestions": 3,
                "abilityAnalysis": "整体表现良好，在词汇理解方面表现突出...",
                "skillBreakdown": [
                    {
                        "skillName": "詞彙理解",
                        "masteryLevel": 0.85,
                        "correctCount": 2,
                        "totalCount": 2,
                        "performanceDescription": "在詞彙理解方面表現出色，能夠準確掌握多義詞在不同語境下的含義"
                    }
                ],
                "strengthsDetailed": [
                    {
                        "skillName": "詞彙理解",
                        "masteryLevel": 0.85,
                        "description": "你在詞彙理解方面表現出色，能夠準確掌握多義詞在不同語境下的含義，對常見詞彙的理解準確到位。",
                        "evidence": ["正確理解了文章中的同義詞替換", "準確識別了關鍵詞的語境含義"]
                    }
                ],
                "weaknessesDetailed": [
                    {
                        "skillName": "推理判斷",
                        "masteryLevel": 0.3,
                        "description": "推理能力有待提升，在根據上下文推斷隱含意思方面存在困難。",
                        "improvementSuggestions": ["多練習根據上下文推斷詞義和句意的題目", "學會識別文章中的邏輯關係"],
                        "practiceFocus": "重點練習推理題型，培養邏輯思維能力"
                    }
                ],
                "strengths": ["詞彙理解", "細節分析"],
                "weaknesses": ["推理判斷"],
                "recommendations": ["多練習推理題型", "注意文章邏輯結構"],
                "timeSpent": 1800
            }
        }


# ===== 查询结果模型 =====

class GradingStatusResponse(BaseModel):
    """批改状态查询响应模型"""
    submission_id: str = Field(..., description="提交ID")
    status: Literal["processing", "completed", "failed"] = Field(..., description="批改状态")
    progress: int = Field(..., description="进度百分比(0-100)")
    message: str = Field(..., description="状态消息")
    result: Optional[AITeacherResponse] = Field(None, description="批改结果(仅当completed时)")
    error_detail: Optional[str] = Field(None, description="错误详情(仅当failed时)")

    class Config:
        json_schema_extra = {
            "example": {
                "submission_id": "submission_20240101_100001",
                "status": "completed",
                "progress": 100,
                "message": "批改完成",
                "result": {
                    "final_score": 0.67,
                    "correct_count": 2,
                    "total_questions": 3
                }
            }
        }


# ===== Demo题目数据响应模型 =====

class DemoQuestionsResponse(BaseModel):
    """Demo题目数据响应模型"""
    passage: DSEPassage = Field(..., description="阅读文章")
    questions: List[DSEQuestion] = Field(..., description="题目列表")
    total_marks: int = Field(..., description="总分")
    estimated_time: int = Field(..., description="建议答题时间(分钟)")

    class Config:
        json_schema_extra = {
            "example": {
                "passage": {
                    "id": "dse-2023-flash-fiction",
                    "title": "Flash Fiction"
                },
                "questions": [],
                "total_marks": 7,
                "estimated_time": 30
            }
        }


# ===== 错误响应模型 =====

class ErrorResponse(BaseModel):
    """统一错误响应模型"""
    error: bool = Field(True, description="错误标识")
    message: str = Field(..., description="错误消息")
    detail: Optional[str] = Field(None, description="错误详情")
    code: Optional[str] = Field(None, description="错误代码")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": True,
                "message": "请求参数无效",
                "detail": "answers字段不能为空",
                "code": "VALIDATION_ERROR"
            }
        }