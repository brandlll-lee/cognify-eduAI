"""
AI Teacher服务

本模块实现DSE英文阅读理解的AI老师功能，是整个Demo系统的核心组件。
AI老师具备以下能力：
1. 精确批改各种题型（选择题、填空题、时序题）
2. 提供详细的错题解析和原文引用
3. 生成个性化的能力分析和学习建议
4. 支持多种技能维度的评估

设计原则：
- 智能批改：基于先进的大语言模型
- 教学导向：不仅判断对错，更注重教学价值
- 个性化：针对学生薄弱环节提供针对性建议
- 可扩展：支持未来更多题型和评估维度
"""

import json
import logging
import httpx
from typing import List, Dict, Any, Optional
import re
from datetime import datetime

from ..models.dse_models import (
    DSEPassage,
    DSEQuestion,
    UserAnswer,
    AITeacherResponse,
    QuestionResult,
    QuestionType,
    SkillType,
    SkillMastery,
    StrengthDetail,
    WeaknessDetail,
)
from ..core.config import get_settings

logger = logging.getLogger(__name__)


class AITeacherService:
    """
    AI Teacher服务类
    
    负责调用OpenRouter API，实现智能批改和教学分析功能。
    使用精心设计的Prompt模板确保批改质量和教学效果。
    """
    
    def __init__(self):
        """初始化AI Teacher服务"""
        self.settings = get_settings()
        self.client = httpx.AsyncClient()
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        
        # AI模型配置
        self.model = "google/gemini-2.5-flash-lite"  # 使用qwen/qwen3-235b-a22b获得最佳效果
        self.max_tokens = 40000
        self.temperature = 0.1  # 低温度确保批改一致性
        
    async def grade_answers(
        self,
        passage: DSEPassage,
        questions: List[DSEQuestion],
        user_answers: List[UserAnswer],
        time_spent: float
    ) -> AITeacherResponse:
        """
        批改用户答案
        
        这是AI Teacher的核心方法，执行完整的批改流程：
        1. 构建批改上下文
        2. 生成专业Prompt
        3. 调用AI模型
        4. 解析批改结果
        5. 生成教学分析
        
        Args:
            passage: 阅读文章
            questions: 题目列表
            user_answers: 用户答案
            time_spent: 答题用时（秒）
            
        Returns:
            AITeacherResponse: 完整的批改结果和教学分析
            
        Raises:
            Exception: AI调用失败或结果解析错误
        """
        logger.info("开始AI批改流程")
        
        try:
            # 1. 构建批改上下文
            context = self._build_grading_context(passage, questions, user_answers, time_spent)
            
            # 2. 生成专业Prompt
            prompt = self._create_grading_prompt(context)
            
            # 3. 调用AI模型
            ai_response = await self._call_ai_model(prompt)
            
            # 4. 解析批改结果
            result = self._parse_ai_response(ai_response, questions, user_answers, context, time_spent)
            
            logger.info("AI批改完成")
            return result
            
        except Exception as e:
            logger.error(f"AI批改失败: {e}")
            # 返回降级结果
            return self._create_fallback_response(questions, user_answers, time_spent)
    
    def _build_grading_context(
        self,
        passage: DSEPassage,
        questions: List[DSEQuestion],
        user_answers: List[UserAnswer],
        time_spent: float
    ) -> Dict[str, Any]:
        """
        构建批改上下文
        
        将所有批改所需的信息整理成结构化的上下文，
        包括文章内容、题目详情、标准答案、用户答案等。
        支持子题目的详细分解以便AI老师进行精确批改。
        
        Args:
            passage: 阅读文章
            questions: 题目列表  
            user_answers: 用户答案
            time_spent: 答题用时
            
        Returns:
            Dict[str, Any]: 结构化的批改上下文
        """
        # 构建用户答案映射
        answer_map = {ans.question_id: ans for ans in user_answers}
        
                # 调试日志：打印用户答案详情
        logger.info("=== 用户答案调试信息 ===")
        for ans in user_answers:
            logger.info(f"题目ID: {ans.question_id}, 类型: {ans.type}")
            
            # 详细检查每种类型的答案
            if hasattr(ans, 'selected_option'):
                logger.info(f"  selected_option: '{ans.selected_option}' (type: {type(ans.selected_option)})")
            if hasattr(ans, 'selectedOption'):
                logger.info(f"  selectedOption: '{ans.selectedOption}' (type: {type(ans.selectedOption)})")
            if hasattr(ans, 'fill_in_answers'):
                logger.info(f"  fill_in_answers: {ans.fill_in_answers}")
            if hasattr(ans, 'fillInAnswers'):
                logger.info(f"  fillInAnswers: {ans.fillInAnswers}")
            if hasattr(ans, 'timeline_answers'):
                logger.info(f"  timeline_answers: {ans.timeline_answers}")
            if hasattr(ans, 'timelineAnswers'):
                logger.info(f"  timelineAnswers: {ans.timelineAnswers}")
                        
        logger.info("=== 调试信息结束 ===")
        
        # 构建题目分析数据
        questions_data = []
        sub_questions_data = []
        sub_question_counter = 1
        
        for question in questions:
            user_answer = answer_map.get(question.id)
            
            # 格式化用户答案
            user_answer_text = self._format_user_answer(question, user_answer)
            
            # 格式化标准答案
            correct_answer_text = self._format_correct_answer(question)
            
            question_data = {
                "question_number": question.questionNumber,
                "question_text": question.questionText,
                "type": question.type.value,
                "skill_type": question.skillType.value,
                "reference_paragraphs": question.referenceParagraphs or [],
                "correct_answer": correct_answer_text,
                "user_answer": user_answer_text,
                "total_marks": question.totalMarks,
                "explanation": question.explanation or ""
            }
            questions_data.append(question_data)
            
            # 分解子题目用于详细批改
            if question.type.value == "fill-in-blank" and question.subQuestions:
                # 填空题：为每个子题创建单独的批改项
                for i, sub_question in enumerate(question.subQuestions):
                    user_sub_answer = ""
                    
                    # 提取用户对该子题的答案 - 支持多种属性名格式
                    raw_sub_answer = ""
                    if user_answer:
                        # 优先使用fillInAnswers（前端格式）
                        if hasattr(user_answer, 'fillInAnswers') and user_answer.fillInAnswers:
                            raw_sub_answer = user_answer.fillInAnswers.get(sub_question.id, "")
                        # 备用fill_in_answers（后端格式）
                        elif hasattr(user_answer, 'fill_in_answers') and user_answer.fill_in_answers:
                            raw_sub_answer = user_answer.fill_in_answers.get(sub_question.id, "")
                        # 兼容字典访问方式
                        elif isinstance(user_answer, dict):
                            fill_answers = user_answer.get('fillInAnswers') or user_answer.get('fill_in_answers') or {}
                            raw_sub_answer = fill_answers.get(sub_question.id, "")
                    
                    # 检查填空题答案是否有效
                    if raw_sub_answer and raw_sub_answer.strip() and raw_sub_answer != "undefined" and raw_sub_answer != "null":
                        user_sub_answer = raw_sub_answer.strip()
                    else:
                        user_sub_answer = "未作答"
                    
                    logger.info(f"填空题答案检查 - {sub_question.id} 原始值: '{raw_sub_answer}', 最终答案: '{user_sub_answer}'")
                    
                    sub_data = {
                        "sub_question_number": sub_question_counter,
                        "parent_question_number": question.questionNumber,
                        "question_text": sub_question.questionText,
                        "type": "fill-in-blank-sub",
                        "skill_type": question.skillType.value,
                        "marks": sub_question.marks,
                        "correct_answer": sub_question.correctAnswer,
                        "user_answer": user_sub_answer,
                        "reference_paragraphs": question.referenceParagraphs or []
                    }
                    sub_questions_data.append(sub_data)
                    
                    # 调试日志
                    logger.info(f"填空子题 {sub_question_counter}: {sub_question.questionText} = 用户答案:'{user_sub_answer}' 正确答案:'{sub_question.correctAnswer}'")
                    sub_question_counter += 1
                    
            elif question.type.value == "timeline-sequencing" and question.correctAnswers:
                # 时序题：为每个位置创建单独的批改项
                user_timeline_answers = {}
                if user_answer:
                    # 优先使用timelineAnswers（前端格式）
                    if hasattr(user_answer, 'timelineAnswers') and user_answer.timelineAnswers:
                        user_timeline_answers = user_answer.timelineAnswers or {}
                    # 备用timeline_answers（后端格式）
                    elif hasattr(user_answer, 'timeline_answers') and user_answer.timeline_answers:
                        user_timeline_answers = user_answer.timeline_answers or {}
                    # 兼容字典访问方式
                    elif isinstance(user_answer, dict):
                        user_timeline_answers = user_answer.get('timelineAnswers') or user_answer.get('timeline_answers') or {}
                
                for position, correct_answer in question.correctAnswers.items():
                    raw_user_answer = user_timeline_answers.get(position, "")
                    
                    # 检查时序题答案是否有效
                    if raw_user_answer and raw_user_answer.strip() and raw_user_answer != "undefined" and raw_user_answer != "null":
                        user_pos_answer = raw_user_answer.strip()
                    else:
                        user_pos_answer = "未作答"
                    
                    logger.info(f"时序题答案检查 - 位置({position}) 原始值: '{raw_user_answer}', 最终答案: '{user_pos_answer}'")
                    
                    sub_data = {
                        "sub_question_number": sub_question_counter,
                        "parent_question_number": question.questionNumber,
                        "question_text": f"位置({position}) - 时序排列",
                        "type": "timeline-sequencing-sub",
                        "skill_type": question.skillType.value,
                        "marks": 1,  # 每个位置1分
                        "correct_answer": correct_answer,
                        "user_answer": user_pos_answer,
                        "reference_paragraphs": question.referenceParagraphs or []
                    }
                    sub_questions_data.append(sub_data)
                    
                    # 调试日志
                    logger.info(f"时序子题 {sub_question_counter}: 位置({position}) = 用户答案:'{user_pos_answer}' 正确答案:'{correct_answer}'")
                    sub_question_counter += 1
                    
            else:
                # 单选题等其他类型：作为单独的子题
                # 重新获取用户答案以确保准确性
                actual_user_answer = "未作答"
                if user_answer:
                    if question.type.value == "multiple-choice":
                        # 多种方式获取选择题答案，注意检查是否为有效答案
                        selected = None
                        if hasattr(user_answer, 'selected_option'):
                            selected = user_answer.selected_option
                        elif hasattr(user_answer, 'selectedOption'):
                            selected = user_answer.selectedOption
                        elif isinstance(user_answer, dict):
                            selected = user_answer.get('selected_option') or user_answer.get('selectedOption')
                        
                        # 检查选择的答案是否有效（不为None、空字符串、"undefined"等）
                        if selected and selected.strip() and selected != "undefined" and selected != "null":
                            actual_user_answer = selected.strip()
                        else:
                            actual_user_answer = "未作答"
                            
                        logger.info(f"选择题答案检查 - 原始值: '{selected}', 最终答案: '{actual_user_answer}'")
                    else:
                        actual_user_answer = user_answer_text
                
                sub_data = {
                    "sub_question_number": sub_question_counter,
                    "parent_question_number": question.questionNumber,
                    "question_text": question.questionText,
                    "type": question.type.value,
                    "skill_type": question.skillType.value,
                    "marks": question.totalMarks,
                    "correct_answer": correct_answer_text,
                    "user_answer": actual_user_answer,
                    "reference_paragraphs": question.referenceParagraphs or []
                }
                sub_questions_data.append(sub_data)
                
                # 调试日志
                logger.info(f"选择题 {sub_question_counter}: 题目{question.questionNumber} = 用户答案:'{actual_user_answer}' 正确答案:'{correct_answer_text}'")
                sub_question_counter += 1
        
        return {
            "passage": {
                "title": passage.title,
                "content": passage.content,
                "word_count": passage.wordCount
            },
            "questions": questions_data,
            "sub_questions": sub_questions_data,
            "time_spent_minutes": round(time_spent / 60, 1),
            "total_questions": len(questions),
            "total_sub_questions": len(sub_questions_data),
            "total_marks": sum(q.totalMarks for q in questions)
        }
    
    def _format_user_answer(self, question: DSEQuestion, user_answer: Optional[UserAnswer]) -> str:
        """格式化用户答案为文本形式"""
        if not user_answer:
            return "未作答"
        
        if question.type == QuestionType.MULTIPLE_CHOICE:
            # 多种方式获取选择题答案
            selected = None
            if hasattr(user_answer, 'selected_option'):
                selected = user_answer.selected_option
            elif hasattr(user_answer, 'selectedOption'):
                selected = user_answer.selectedOption
            elif isinstance(user_answer, dict):
                selected = user_answer.get('selected_option') or user_answer.get('selectedOption')
            
            # 检查选择的答案是否有效
            if selected and selected.strip() and selected != "undefined" and selected != "null":
                return selected.strip()
            else:
                return "未作答"
        
        elif question.type == QuestionType.FILL_IN_BLANK:
            # 获取填空题答案 - 支持多种格式
            fill_answers = {}
            if hasattr(user_answer, 'fillInAnswers') and user_answer.fillInAnswers:
                fill_answers = user_answer.fillInAnswers
            elif hasattr(user_answer, 'fill_in_answers') and user_answer.fill_in_answers:
                fill_answers = user_answer.fill_in_answers
            elif isinstance(user_answer, dict):
                fill_answers = user_answer.get('fillInAnswers') or user_answer.get('fill_in_answers') or {}
            
            if not fill_answers:
                return "未作答"
            
            answers = []
            for sub_q in question.subQuestions or []:
                answer = fill_answers.get(sub_q.id, "")
                answers.append(f"{sub_q.questionText}: {answer or '未作答'}")
            return "; ".join(answers)
        
        elif question.type == QuestionType.TIMELINE_SEQUENCING:
            # 获取时序题答案 - 支持多种格式
            timeline_answers = {}
            if hasattr(user_answer, 'timelineAnswers') and user_answer.timelineAnswers:
                timeline_answers = user_answer.timelineAnswers
            elif hasattr(user_answer, 'timeline_answers') and user_answer.timeline_answers:
                timeline_answers = user_answer.timeline_answers
            elif isinstance(user_answer, dict):
                timeline_answers = user_answer.get('timelineAnswers') or user_answer.get('timeline_answers') or {}
            
            if not timeline_answers:
                return "未作答"
            
            answers = []
            for event in question.timelineEvents or []:
                if event.position != "fixed":
                    answer = timeline_answers.get(event.position, "")
                    answers.append(f"{event.position}: {answer or '未作答'}")
            return "; ".join(answers)
        
        return "未作答"
    
    def _format_correct_answer(self, question: DSEQuestion) -> str:
        """格式化标准答案为文本形式"""
        if question.type == QuestionType.MULTIPLE_CHOICE:
            return question.correctAnswer or ""
        
        elif question.type == QuestionType.FILL_IN_BLANK:
            if not question.subQuestions:
                return ""
            
            answers = []
            for sub_q in question.subQuestions:
                answers.append(f"{sub_q.questionText}: {sub_q.correctAnswer}")
            return "; ".join(answers)
        
        elif question.type == QuestionType.TIMELINE_SEQUENCING:
            if not question.correctAnswers:
                return ""
            
            answers = []
            for pos, letter in question.correctAnswers.items():
                answers.append(f"{pos}: {letter}")
            return "; ".join(answers)
        
        return ""
    
    def _create_grading_prompt(self, context: Dict[str, Any]) -> str:
        """
        创建AI批改Prompt
        
        这是AI Teacher的核心Prompt模板，经过精心设计以确保：
        1. 准确的批改结果
        2. 高质量的教学解析
        3. 个性化的学习建议
        4. 结构化的JSON输出
        5. 详细的能力分析数据
        
        Args:
            context: 批改上下文数据
            
        Returns:
            str: 完整的批改Prompt
        """
        
        prompt = f"""你係蘭老師，一位擁有15年以上教學經驗嘅香港DSE英語閱讀理解名師。你用正宗嘅香港粵語同繁體中文為學生提供專業嘅批改同指導。

## 📚 閱讀文章資訊
**標題**: {context['passage']['title']}
**字數**: {context['passage']['word_count']}字

**文章內容**（請仔細閱讀，呢個係批改嘅核心依據）:
{context['passage']['content']}

## 📝 題目同答案分析
今次需要批改{context['total_sub_questions']}道小題（來自{context['total_questions']}道大題，總分{context['total_marks']}分）：

"""
        
        # 添加每道子题目的详细信息
        for sub_q in context['sub_questions']:
            prompt += f"""
### 小題{sub_q['sub_question_number']} - 來自第{sub_q['parent_question_number']}題 ({sub_q['marks']}分)
**題目類型**: {self._get_type_description(sub_q['type'])}
**考查技能**: {self._get_skill_description(sub_q['skill_type'])}
**題目**: {sub_q['question_text']}
**標準答案**: {sub_q['correct_answer']}
**學生答案**: {sub_q['user_answer']}
**參考段落**: {', '.join(sub_q['reference_paragraphs']) if sub_q['reference_paragraphs'] else '全文'}

"""
        
        prompt += f"""
## 🎯 智能批改要求（專業提示詞工程版）

### 1. 答案判斷標準
- **選擇題**: 選項必須同標準答案完全一致
- **填空題**: 答案需語義正確，接受合理同義詞
- **時序題**: 字母同位置對應必須100%準確

### 2. 📝 解析內容要求（智能長度控制）

**🔥 錯題解析（詳細）**：如果學生答錯，必須提供詳細分析：
- 【原文定位】明確引用相關段落，提供中文翻譯，解釋關鍵詞
- 【解題思路】說明正確嘅解題步驟同推理過程
- 【錯誤分析】分析學生答案錯誤原因，指出思維偏差，提供改進建議
- 【技巧提醒】總結該題型嘅解題技巧同注意事項

**✅ 正確題解析（簡潔）**：如果學生答對，提供簡潔確認：
- 【原文定位】簡要引用相關段落
- 【解題思路】簡單說明正確推理
- 【技巧提醒】簡短提供該題型技巧

### 3. 📊 詳細能力評估（重點升級）

**🎯 智能技能分類系統**：
根據學生實際答題表現，智能識別和評估相關技能維度。你可以靈活選擇以下技能分類，也可以根據題目特點創新設計：

**核心技能維度建議**：
- **vocabulary** (詞彙理解): 同義詞替換、多義詞理解、語境推斷
- **detail** (細節理解): 事實信息定位、數據提取、具體內容理解
- **inference** (推理判斷): 隱含意思推斷、邏輯關係理解、作者意圖分析
- **main-idea** (主旨大意): 段落主題、文章中心思想、觀點總結
- **structure** (文章結構): 段落關係、邏輯順序、文章組織方式
- **sequencing** (時序邏輯): 事件順序、時間關係、因果邏輯

**創新技能維度**（可根據文章類型靈活添加）：
- **cultural-context** (文化語境): 文化背景理解、習俗認知
- **critical-thinking** (批判思維): 觀點評析、論證理解
- **emotional-tone** (情感語調): 作者態度、情感色彩理解
- **scientific-reasoning** (科學推理): 科學邏輯、實驗分析（適用於科學類文章）
- **narrative-structure** (敘事結構): 故事情節、人物發展（適用於故事類文章）

**📈 精確掌握度計算**：
🚨 **重要提醒**：必須嚴格按照學生實際答題情況計算統計數據
- correct_count: 該技能相關題目中學生答對的數量（必須準確）
- total_count: 該技能相關題目的總數量（必須準確）  
- mastery_level: correct_count / total_count（確保計算正確）

**📝 計算檢查清單**：
1. 仔細檢查每道題目的答對/答錯狀態
2. 按技能分類歸納相關題目
3. 準確統計各技能的答對數和總數
4. 計算掌握度 = 答對數 ÷ 總數
5. 確保所有數字邏輯一致

**🔍 詳細分析要求**：
1. **優勢技能**：掌握度 ≥ 0.7 的技能
   - 提供具體的表現描述
   - 列舉支撐證據（具體答對的題目或表現）
   - 給出進一步提升建議

2. **薄弱技能**：掌握度 < 0.6 的技能
   - 分析具體問題所在
   - 提供針對性改進建議（至少3條）
   - 指出練習重點和方法

### 4. 💡 個性化學習建議
基於錯題模式和能力短板提供3-5條針對性建議

## ⏰ 時間分析
學生用時: {context['time_spent_minutes']:.1f}分鐘，建議時間: 25-30分鐘

## 📤 詳細輸出格式要求

🚨 **嚴格執行以下指令** 🚨

**📋 JSON格式規範**:
1. 🔒 只能返回JSON格式，禁止添加任何非JSON內容
2. 🔒 JSON必須以 {{ 開始，以 }} 結束
3. 🔒 禁止使用markdown代碼塊標記
4. 🔒 JSON結束後立即停止輸出

**📝 智能內容控制**:
- **錯題**: explanation字段包含【原文定位】【解題思路】【錯誤分析】【技巧提醒】四部分，內容詳細
- **正確題**: explanation字段包含【原文定位】【解題思路】【技巧提醒】三部分，內容簡潔
- 每個部分之間用<br><br>分隔
- 所有內容用香港粵語/繁體中文表達
- is_correct字段必須同explanation分析保持一致
- user_answer字段必須準確反映學生實際答案

```json
{{
  "results": [
    {{
      "question_number": 1,
      "is_correct": true,
      "user_answer": "limits",
      "correct_answer": "limits", 
      "explanation": "【原文定位】根據第[2]段'Flash fiction is a category of short story that limits the author'，呢度嘅limits同題目restrict係同義詞。<br><br>【解題思路】填空題考同義詞替換，restrict表示限制，原文limits意思一樣。<br><br>【技巧提醒】填空題要注意同義詞替換，檢查語法形式。",
      "skill_analysis": "詞彙理解能力：能夠識別同義詞替換",
      "reference_text": "Flash fiction is a category of short story that limits the author to a word count of 1,000 words or less."
    }},
    {{
      "question_number": 2,
      "is_correct": false,
      "user_answer": "fake",
      "correct_answer": "solid",
      "explanation": "【原文定位】根據第[3]段'Following the tips below will guide you in writing a solid flash fiction story'，呢度solid（紮實）係形容詞，表示故事結構穩固。<br><br>【解題思路】題目要求同strong意思相近嘅詞，solid有紮實、穩固意思，同strong（有力）語義接近。<br><br>【錯誤分析】學生填fake（虛假），意思完全相反。Solid有多重意思：固體、紮實等，學生可能只知道固體意思。需要根據語境判斷詞義，fake係負面詞，solid係正面詞，完全唔符合讚賞故事質素嘅語境。<br><br>【技巧提醒】形容詞填空要理解語境正負面，學習多義詞喺唔同語境嘅用法。",
      "skill_analysis": "詞彙理解能力：對多義詞的理解不足，未能根據語境選擇正確含義",
      "reference_text": "Following the tips below will guide you in writing a solid flash fiction story."
    }}
  ],
  "final_score": 0.57,
  "correct_count": 4,
  "total_questions": 7,
  "ability_analysis": "學生喺詞彙理解方面表現幾好，能夠準確識別同義詞。喺細節理解上有一定基礎，但係喺時序邏輯方面需要加強練習。整體答題思路清晰，但需要提高對複雜語境的理解能力。",
  
  "skill_breakdown": [
    {{
      "skill_name": "詞彙理解",
      "mastery_level": 0.85,
      "correct_count": 2,
      "total_count": 2,
      "performance_description": "在詞彙理解方面表現出色，能夠準確掌握多義詞在不同語境下的含義，對同義詞替換有良好的敏感度。"
    }},
    {{
      "skill_name": "細節理解",
      "mastery_level": 0.67,
      "correct_count": 2,
      "total_count": 3,
      "performance_description": "細節定位能力較好，能夠準確找到關鍵信息，但在處理複雜細節時偶有疏漏。"
    }},
    {{
      "skill_name": "時序邏輯",
      "mastery_level": 0.33,
      "correct_count": 1,
      "total_count": 3,
      "performance_description": "時序邏輯理解存在較大困難，對事件先後順序的把握不夠準確，需要加強練習。"
    }}
  ],
  
  "strengths_detailed": [
    {{
      "skill_name": "詞彙理解",
      "mastery_level": 0.85,
      "description": "你在詞彙理解方面表現出色，能夠準確掌握多義詞在不同語境下的含義，對常見詞彙的理解準確到位。特別是在同義詞替換和語境推斷方面表現優異。",
      "evidence": [
        "正確理解了文章中'limits'同'restrict'的同義關係",
        "準確識別了關鍵詞在特定語境下的含義",
        "表現出對詞彙語法形式變化的敏感度"
      ]
    }}
  ],
  
  "weaknesses_detailed": [
    {{
      "skill_name": "時序邏輯",
      "mastery_level": 0.33,
      "description": "時序邏輯理解是你目前的主要弱項。在理解事件發生的先後順序、把握時間關係和邏輯順序方面存在較大困難，這影響了對文章整體結構的理解。",
      "improvement_suggestions": [
        "閱讀時專門標注時間標誌詞，如before, after, then, meanwhile等",
        "練習畫時間線，將文章中的重要事件按時間順序排列",
        "多做時序排列專項練習，從簡單的事件順序開始",
        "學會識別因果關係詞，理解邏輯關係對時序的影響"
      ],
      "practice_focus": "重點練習時序排列題型，建議每天花15分鐘專門練習事件排序，培養時間邏輯思維"
    }}
  ],
  
  "strengths": ["詞彙理解", "細節理解"],
  "weaknesses": ["時序邏輯"], 
  "recommendations": [
    "重點練習時序排列題，注意把握事件先後順序",
    "閱讀時畫出時間線，標記重要事件發生時間",
    "學習識別時間連接詞如before, after, then等",
    "多練習邏輯關係的理解，提高推理能力"
  ],
  "time_spent": {int(context['time_spent_minutes'] * 60)}
}}
```

**📋 執行指令**: 
1. 為每道小題(question_number從1到{context['total_sub_questions']})提供批改結果
2. 確保is_correct字段與explanation內容完全一致
3. 為每個出現的技能提供skill_breakdown條目
4. 為掌握度≥0.7的技能提供strengths_detailed條目
5. 為掌握度<0.6的技能提供weaknesses_detailed條目
6. 返回JSON格式批改結果，JSON結束後立即停止輸出

🔥 **專業能力分析**：
- 精確計算每個技能的掌握度
- 提供具體而專業的表現描述
- 給出可操作的改進建議
- 確保分析的教學價值和實用性"""

        return prompt
    
    def _get_type_description(self, question_type: str) -> str:
        """获取题目类型的中文描述"""
        type_map = {
            "multiple-choice": "选择题",
            "fill-in-blank": "填空题", 
            "timeline-sequencing": "时序排列题"
        }
        return type_map.get(question_type, question_type)
    
    def _get_skill_description(self, skill_type: str) -> str:
        """获取技能类型的中文描述"""
        skill_map = {
            "vocabulary": "词汇理解",
            "detail": "细节理解",
            "inference": "推理判断",
            "main-idea": "主旨大意",
            "structure": "文章结构",
            "sequencing": "时序逻辑"
        }
        return skill_map.get(skill_type, skill_type)
    
    async def _call_ai_model(self, prompt: str) -> str:
        """
        调用AI模型进行批改
        
        使用OpenRouter API调用Claude 3.5 Sonnet模型。
        配置了适当的参数以确保批改质量和稳定性。
        
        Args:
            prompt: 批改Prompt
            
        Returns:
            str: AI模型的响应文本
            
        Raises:
            Exception: API调用失败
        """
        headers = {
            "Authorization": f"Bearer {self.settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.settings.APP_NAME,
            "X-Title": "DSE AI Teacher"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": 1,
            "frequency_penalty": 0,
            "presence_penalty": 0
        }
        
        logger.info(f"调用AI模型: {self.model}")
        
        try:
            response = await self.client.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=120  # 2分钟超时
            )
            
            response.raise_for_status()
            data = response.json()
            
            if "choices" not in data or not data["choices"]:
                raise Exception("AI响应格式错误：缺少choices字段")
            
            content = data["choices"][0]["message"]["content"]
            logger.info("AI模型调用成功")
            
            return content
            
        except httpx.HTTPStatusError as e:
            logger.error(f"AI API调用失败: {e.response.status_code} - {e.response.text}")
            raise Exception(f"AI服务暂时不可用: {e.response.status_code}")
        
        except httpx.TimeoutException:
            logger.error("AI API调用超时")
            raise Exception("AI服务响应超时，请重试")
        
        except Exception as e:
            logger.error(f"AI API调用异常: {e}")
            raise Exception(f"AI服务异常: {str(e)}")
    
    def _parse_ai_response(
        self,
        ai_response: str,
        questions: List[DSEQuestion],
        user_answers: List[UserAnswer],
        context: Dict[str, Any],
        time_spent: float
    ) -> AITeacherResponse:
        """
        解析AI响应结果
        
        从AI的文本响应中提取JSON格式的批改结果，
        并转换为标准的AITeacherResponse模型。
        
        Args:
            ai_response: AI的原始响应文本
            questions: 题目列表
            time_spent: 答题用时
            
        Returns:
            AITeacherResponse: 解析后的批改结果
            
        Raises:
            Exception: JSON解析失败或数据格式错误
        """
        try:
            # 多种方式提取JSON内容
            json_str = None
            
            # 首先尝试使用括号匹配算法查找完整的JSON对象（最可靠）
            logger.info(f"AI响应长度: {len(ai_response)}")
            logger.info(f"AI响应开头: {ai_response[:200]}...")
            logger.info(f"AI响应结尾: ...{ai_response[-200:]}")
            
            json_str = self._extract_json_object(ai_response)
            if json_str:
                logger.info(f"括号匹配成功，提取JSON长度: {len(json_str)}")
            else:
                logger.warning("括号匹配失败，尝试正则表达式")
            
            # 如果括号匹配失败，再尝试多种正则表达式策略
            if not json_str:
                logger.info("括号匹配失败，尝试多种正则表达式策略")
                
                # 策略1: 查找```json到```的内容，然后手动解析
                json_block_pattern = r'```json\s*(\{.*?)```'
                json_match = re.search(json_block_pattern, ai_response, re.DOTALL)
                if json_match:
                    potential_json = json_match.group(1).strip()
                    logger.info(f"找到JSON代码块，长度: {len(potential_json)}")
                    # 尝试找到最后一个完整的}
                    json_str = self._try_repair_incomplete_json(potential_json)
                    if json_str:
                        logger.info("策略1成功：修复不完整JSON")
                
                # 策略2: 查找第一个{到最后一个}
                if not json_str:
                    start_pos = ai_response.find('{')
                    if start_pos != -1:
                        # 找到最后一个可能的}位置
                        for end_pos in range(len(ai_response) - 1, start_pos, -1):
                            if ai_response[end_pos] == '}':
                                potential_json = ai_response[start_pos:end_pos + 1]
                                try:
                                    json.loads(potential_json)
                                    json_str = potential_json
                                    logger.info("策略2成功：找到完整JSON")
                                    break
                                except:
                                    continue
                
                # 策略3: 尝试修复常见的JSON问题
                if not json_str:
                    start_pos = ai_response.find('{')
                    if start_pos != -1:
                        # 获取从{开始的所有内容
                        raw_json = ai_response[start_pos:]
                        json_str = self._try_repair_incomplete_json(raw_json)
                        if json_str:
                            logger.info("策略3成功：修复JSON格式")
            
            if not json_str:
                logger.error(f"无法从AI响应中提取JSON: {ai_response[:500]}...")
                raise Exception("AI响应格式错误：未找到有效的JSON数据")
            
            # 清理JSON字符串
            json_str = json_str.strip()
            logger.debug(f"提取到的JSON字符串长度: {len(json_str)}")
            logger.debug(f"JSON开头: {json_str[:100]}...")
            
            # 记录AI原始响应用于调试
            logger.info(f"=== AI原始响应调试 ===")
            logger.info(f"完整响应: {ai_response}")
            logger.info(f"提取的JSON: {json_str}")
            logger.info(f"=== AI原始响应调试结束 ===")
            
            # 多策略JSON解析，确保最大兼容性
            result_data = None
            parse_strategies = [
                ("直接解析", lambda x: json.loads(x)),
                ("引号修复解析", lambda x: json.loads(self._fix_quotes_in_json(x))),
                ("深度引号修复解析", lambda x: json.loads(self._deep_fix_quotes(x))),
                ("格式修复解析", lambda x: json.loads(self._fix_json_format(x))),
                ("强制清理解析", lambda x: json.loads(self._force_clean_json(x))),
                ("容错解析", lambda x: self._tolerant_json_parse(x))
            ]
            
            for strategy_name, parse_func in parse_strategies:
                try:
                    result_data = parse_func(json_str)
                    logger.info(f"JSON解析成功: {strategy_name}")
                    break
                except (json.JSONDecodeError, ValueError, Exception) as e:
                    logger.warning(f"{strategy_name}失败: {e}")
                    if "char" in str(e):
                        # 详细记录错误位置
                        char_pos = str(e).split("char ")[1].split(")")[0] if "char " in str(e) else "未知"
                        logger.warning(f"错误字符位置: {char_pos}")
                        # 显示错误位置周围的字符
                        try:
                            pos = int(char_pos)
                            start = max(0, pos - 50)
                            end = min(len(json_str), pos + 50)
                            logger.warning(f"错误位置上下文: '{json_str[start:end]}'")
                        except:
                            pass
                    continue
            
            if result_data is None:
                logger.error("所有JSON解析策略均失败")
                raise Exception("AI响应JSON格式严重错误，无法解析")
            
            # 记录解析后的关键数据
            logger.info(f"=== AI解析后数据调试 ===")
            logger.info(f"结果数量: {len(result_data.get('results', []))}")
            logger.info(f"正确题数: {result_data.get('correct_count', 0)}")
            logger.info(f"总题数: {result_data.get('total_questions', 0)}")
            logger.info(f"最终得分: {result_data.get('final_score', 0)}")
            
            # 显示每个结果的详细信息
            for i, result in enumerate(result_data.get('results', [])):
                logger.info(f"结果{i+1}: 题号{result.get('question_number')} 正确性:{result.get('is_correct')} 用户答案:'{result.get('user_answer')}' 正确答案:'{result.get('correct_answer')}'")
                
                # 处理explanation字段，可能是字符串或字典
                explanation = result.get('explanation', '')
                if isinstance(explanation, dict):
                    # 如果是字典，转换为字符串显示
                    explanation_str = str(explanation)[:200]
                    logger.info(f"  解析内容(字典格式): {explanation_str}...")
                elif isinstance(explanation, str):
                    logger.info(f"  解析内容: {explanation[:200]}...")
                else:
                    logger.info(f"  解析内容: {str(explanation)[:200]}...")
            logger.info(f"=== AI解析后数据调试结束 ===")
            
            # 处理explanation字段格式
            self._process_explanation_format(result_data)
            
            # 验证必要字段
            required_fields = ["results", "final_score", "correct_count", "total_questions"]
            for field in required_fields:
                if field not in result_data:
                    raise Exception(f"AI响应缺少必要字段: {field}")
            
            # 🚨 修复用户答案错误：验证AI返回的用户答案与实际输入是否一致
            logger.info("=== 用户答案验证与修正 ===")
            self._validate_and_fix_user_answers(result_data, context)
            logger.info("=== 用户答案验证与修正完成 ===")
            
            # 构建QuestionResult列表
            question_results = []
            for result in result_data["results"]:
                question_result = QuestionResult(
                    question_number=result["question_number"],
                    is_correct=result["is_correct"],
                    user_answer=result["user_answer"],
                    correct_answer=result["correct_answer"],
                    explanation=result.get("explanation", ""),
                    skill_analysis=result.get("skill_analysis", ""),
                    reference_text=result.get("reference_text")
                )
                question_results.append(question_result)
            
            # 构建完整响应
            ai_teacher_response = AITeacherResponse(
                results=question_results,
                final_score=float(result_data["final_score"]),
                correct_count=int(result_data["correct_count"]),
                total_questions=int(result_data["total_questions"]),
                ability_analysis=result_data.get("ability_analysis", ""),
                
                # 新增：處理詳細能力分析數據
                skill_breakdown=result_data.get("skill_breakdown", []),
                strengths_detailed=result_data.get("strengths_detailed", []),
                weaknesses_detailed=result_data.get("weaknesses_detailed", []),
                
                # 保留原有字段
                strengths=result_data.get("strengths", []),
                weaknesses=result_data.get("weaknesses", []),
                recommendations=result_data.get("recommendations", []),
                time_spent=int(result_data.get("time_spent", time_spent))
            )
            
            # 验证响应结构
            self._validate_ai_response(ai_teacher_response, questions)
            
            # 🚨 修复AI逻辑一致性错误：检查is_correct与explanation的一致性
            logger.info(f"=== AI逻辑一致性检查 ===")
            logic_fixes = 0
            for i, result in enumerate(ai_teacher_response.results):
                explanation_lower = result.explanation.lower()
                user_answer_lower = result.user_answer.lower() if result.user_answer else ""
                correct_answer_lower = result.correct_answer.lower() if result.correct_answer else ""
                
                # 检查逻辑一致性
                has_error_keywords = any(keyword in explanation_lower for keyword in [
                    "错误", "不符", "不正确", "不对", "失误", "问题", "偏差", "不匹配", "不一致", "不当"
                ])
                
                has_correct_keywords = any(keyword in explanation_lower for keyword in [
                    "正确", "准确", "成功", "符合", "一致", "匹配", "对应", "恰当", "合适"
                ])
                
                # 答案是否真的相等（忽略大小写和空格）
                answers_match = user_answer_lower.strip() == correct_answer_lower.strip()
                
                # 检测逻辑错误情况
                if result.is_correct and has_error_keywords and not answers_match:
                    logger.warning(f"题目{result.question_number}: 检测到AI逻辑错误 - is_correct为True但explanation显示错误")
                    logger.warning(f"  用户答案: '{result.user_answer}' vs 正确答案: '{result.correct_answer}'")
                    logger.warning(f"  错误关键词: {[kw for kw in ['错误', '不符', '不正确'] if kw in explanation_lower]}")
                    result.is_correct = False
                    logic_fixes += 1
                    
                elif not result.is_correct and has_correct_keywords and answers_match:
                    logger.warning(f"题目{result.question_number}: 检测到AI逻辑错误 - is_correct为False但explanation显示正确")
                    logger.warning(f"  用户答案: '{result.user_answer}' vs 正确答案: '{result.correct_answer}'")
                    result.is_correct = True
                    logic_fixes += 1
                    
                elif not result.is_correct and not has_error_keywords and answers_match:
                    logger.warning(f"题目{result.question_number}: 检测到潜在逻辑错误 - 答案匹配但is_correct为False")
                    result.is_correct = True
                    logic_fixes += 1
                    
                logger.info(f"题目{result.question_number}: is_correct={result.is_correct}, 答案匹配={answers_match}")
            
            if logic_fixes > 0:
                logger.warning(f"修复了{logic_fixes}个AI逻辑一致性错误")
            else:
                logger.info("AI逻辑一致性检查通过")
            logger.info(f"=== AI逻辑一致性检查完成 ===")

            # 🚨 修复AI计算错误：重新计算正确题数和得分
            logger.info(f"=== AI计算错误修复 ===")
            actual_correct_count = sum(1 for result in ai_teacher_response.results if result.is_correct)
            actual_score = actual_correct_count / len(ai_teacher_response.results) if ai_teacher_response.results else 0
            
            logger.info(f"AI返回的正确题数: {ai_teacher_response.correct_count}")
            logger.info(f"实际正确题数: {actual_correct_count}")
            logger.info(f"AI返回的得分: {ai_teacher_response.final_score:.3f}")
            logger.info(f"实际得分: {actual_score:.3f}")
            
            if ai_teacher_response.correct_count != actual_correct_count or abs(ai_teacher_response.final_score - actual_score) > 0.01:
                logger.warning("检测到AI计算错误，使用后端修正结果")
                ai_teacher_response.correct_count = actual_correct_count
                ai_teacher_response.final_score = actual_score
            logger.info(f"=== AI计算错误修复完成 ===")
            
            # 🚨 修复AI技能分析错误：验证和重建skill_breakdown数据
            logger.info(f"=== AI技能分析验证与修正 ===")
            self._validate_and_fix_skill_analysis(ai_teacher_response, context)
            logger.info(f"=== AI技能分析验证与修正完成 ===")
            
            logger.info("AI响应解析成功")
            return ai_teacher_response
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            logger.error(f"AI响应内容: {ai_response}")
            raise Exception("AI响应格式错误，无法解析批改结果")
        
        except Exception as e:
            logger.error(f"解析AI响应失败: {e}")
            raise Exception(f"处理批改结果时发生错误: {str(e)}")
    
    def _validate_ai_response(self, response: AITeacherResponse, questions: List[DSEQuestion]) -> None:
        """
        验证AI响应的结构和内容是否正确
        
        Args:
            response: AI老师响应
            questions: 原始题目列表
            
        Raises:
            Exception: 当响应结构有问题时
        """
        # 计算预期的子题数量
        expected_sub_questions = 0
        for question in questions:
            if question.type.value == "fill-in-blank" and question.subQuestions:
                expected_sub_questions += len(question.subQuestions)
            elif question.type.value == "timeline-sequencing" and question.correctAnswers:
                expected_sub_questions += len(question.correctAnswers)
            else:
                expected_sub_questions += 1
        
        # 验证结果数量
        actual_results = len(response.results)
        if actual_results != expected_sub_questions:
            logger.warning(f"AI响应结果数量不匹配: 预期{expected_sub_questions}，实际{actual_results}")
        
        # 验证总题数
        if response.total_questions != expected_sub_questions:
            logger.warning(f"AI响应总题数不匹配: 预期{expected_sub_questions}，实际{response.total_questions}")
        
        # 验证结果编号连续性
        result_numbers = [r.question_number for r in response.results]
        expected_numbers = list(range(1, expected_sub_questions + 1))
        if sorted(result_numbers) != expected_numbers:
            logger.warning(f"AI响应题目编号不连续: 预期{expected_numbers}，实际{sorted(result_numbers)}")
        
        logger.info(f"AI响应验证完成: {actual_results}道子题，总分{response.final_score:.2f}")
    
    def _fix_quotes_in_json(self, json_str: str) -> str:
        """
        修复JSON中字符串字段的引号问题
        
        使用简单有效的方法处理AI返回的JSON中包含未转义引号的问题。
        
        Args:
            json_str: 原始JSON字符串
            
        Returns:
            str: 修复后的JSON字符串
        """
        logger.info("开始修复JSON引号问题")
        
        # 方法1：处理字段值中的引号
        # 针对常见的引号问题进行修复
        try:
            # 替换在字段值中明显错误的引号模式
            import re
            
            # 修复类似 "So, if anyone is interested, raise your hand now ." 的引号问题
            # 查找在字段值中间出现的未转义引号
            def fix_quotes_in_field_value(match):
                field_name = match.group(1)
                field_content = match.group(2)
                
                # 简单的引号转义：将字段值中的引号转义
                escaped_content = field_content.replace('\\"', '"')  # 先去掉已有转义
                escaped_content = escaped_content.replace('"', '\\"')  # 重新转义所有引号
                
                return f'"{field_name}": "{escaped_content}"'
            
            # 修复explanation字段
            json_str = re.sub(
                r'"(explanation)"\s*:\s*"([^"]*(?:"[^"]*)*)"',
                fix_quotes_in_field_value,
                json_str,
                flags=re.DOTALL
            )
            
            # 修复reference_text字段
            json_str = re.sub(
                r'"(reference_text)"\s*:\s*"([^"]*(?:"[^"]*)*)"',
                fix_quotes_in_field_value,
                json_str,
                flags=re.DOTALL
            )
            
        except Exception as e:
            logger.warning(f"正则表达式修复失败: {e}")
        
        # 方法2：简单的字符替换修复
        try:
            # 修复一些常见的引号问题模式
            problematic_patterns = [
                # 修复类似 "So, if anyone is interested, raise your hand now ... how about you Timothy?" 的引号
                (r'(\w+)\s*"([^"]*how about you[^"]*)"', r'\1 \\"\2\\"'),
                # 修复其他常见的英文引用
                (r'"([^"]*(?:droned on|interested|raise your hand)[^"]*)"([,\s]*")', r'\\"\1\\"\2'),
            ]
            
            for pattern, replacement in problematic_patterns:
                json_str = re.sub(pattern, replacement, json_str, flags=re.DOTALL)
                
        except Exception as e:
            logger.warning(f"模式替换修复失败: {e}")
        
        logger.info("JSON引号修复完成")
        return json_str
    
    def _deep_fix_quotes(self, json_str: str) -> str:
        """
        深度修复JSON引号问题
        
        使用更激进的方法修复所有可能的引号问题。
        """
        logger.info("开始深度JSON引号修复")
        
        try:
            # 方法：逐个字符解析，智能处理引号
            result = []
            i = 0
            in_string = False
            current_field = ""
            problematic_fields = {"explanation", "reference_text", "ability_analysis"}
            
            while i < len(json_str):
                char = json_str[i]
                
                if char == '"':
                    if not in_string:
                        # 开始一个字符串
                        in_string = True
                        result.append(char)
                        
                        # 检查是否是字段名
                        temp_field = ""
                        j = i + 1
                        while j < len(json_str) and json_str[j] != '"':
                            temp_field += json_str[j]
                            j += 1
                        
                        if temp_field in problematic_fields:
                            current_field = temp_field
                        else:
                            current_field = ""
                        
                    else:
                        # 结束一个字符串，但需要检查是否在问题字段中
                        if current_field and i > 0:
                            # 检查前一个字符是否是转义符
                            if json_str[i-1] != '\\':
                                # 检查下一个字符，判断是否真的是字段结束
                                next_non_space = i + 1
                                while next_non_space < len(json_str) and json_str[next_non_space] in ' \t\n\r':
                                    next_non_space += 1
                                
                                if next_non_space < len(json_str) and json_str[next_non_space] in ',}]':
                                    # 确实是字段结束
                                    in_string = False
                                    current_field = ""
                                    result.append(char)
                                else:
                                    # 可能是字段值内部的引号，需要转义
                                    result.append('\\"')
                            else:
                                # 已经转义的引号
                                in_string = False
                                result.append(char)
                        else:
                            # 普通字段结束
                            in_string = False
                            result.append(char)
                
                elif char == '\\' and in_string:
                    # 转义字符，保持原样
                    result.append(char)
                    if i + 1 < len(json_str):
                        i += 1
                        result.append(json_str[i])
                
                else:
                    result.append(char)
                
                i += 1
            
            fixed_json = ''.join(result)
            logger.info("深度JSON引号修复完成")
            return fixed_json
            
        except Exception as e:
            logger.warning(f"深度引号修复失败: {e}")
            return json_str
    
    def _fix_json_format(self, json_str: str) -> str:
        """
        强化JSON格式修复
        
        Args:
            json_str: 原始JSON字符串
            
        Returns:
            str: 修复后的JSON字符串
        """
        logger.info("开始强化JSON格式修复")
        
        # 第1步：基础清理
        json_str = json_str.replace('\ufeff', '')  # 移除BOM
        json_str = json_str.strip()  # 移除前后空白
        
        # 第2步：深度控制字符清理
        json_str = self._clean_json_control_characters(json_str)
        
        # 第3步：修复常见JSON语法问题
        # 修复尾部逗号
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
        
        # 修复多余的换行和空格
        json_str = re.sub(r'\n\s*\n', '\n', json_str)
        
        # 第4步：特殊字符转义
        # 确保引号内的特殊字符被正确转义
        def escape_special_chars(match):
            content = match.group(1)
            # 转义反斜杠和引号
            content = content.replace('\\', '\\\\').replace('"', '\\"')
            # 转义换行符和制表符
            content = content.replace('\n', '\\n').replace('\t', '\\t').replace('\r', '\\r')
            return f'"{content}"'
        
        # 谨慎处理字符串内容
        try:
            # 只处理简单的引号内容，避免复杂的转义情况
            simple_strings = re.findall(r'"([^"\\]*)"', json_str)
            logger.info(f"找到{len(simple_strings)}个简单字符串")
        except Exception as e:
            logger.warning(f"字符串处理失败: {e}")
        
        logger.info("JSON格式修复完成")
        return json_str
    
    def _force_clean_json(self, json_str: str) -> str:
        """
        强制清理JSON，删除所有可能有问题的字符
        
        Args:
            json_str: 原始JSON字符串
            
        Returns:
            str: 强制清理后的JSON字符串
        """
        logger.info("开始强制JSON清理")
        
        # 只保留基本的ASCII字符和必要的Unicode字符
        clean_chars = []
        for char in json_str:
            char_code = ord(char)
            # 保留基本可打印字符、空格、换行、制表符
            if (32 <= char_code <= 126) or char_code in [9, 10, 13]:
                clean_chars.append(char)
            # 保留中文字符范围
            elif 0x4e00 <= char_code <= 0x9fff:
                clean_chars.append(char)
            # 其他Unicode字符谨慎保留
            elif char_code > 127:
                clean_chars.append(char)
        
        cleaned = ''.join(clean_chars)
        logger.info(f"强制清理完成，从{len(json_str)}字符减少到{len(cleaned)}字符")
        return cleaned
    
    def _tolerant_json_parse(self, json_str: str) -> dict:
        """
        容错JSON解析，尝试各种修复策略
        
        Args:
            json_str: JSON字符串
            
        Returns:
            dict: 解析结果
        """
        logger.info("开始容错JSON解析")
        
        # 策略1：逐步去除可能的问题字符
        for remove_char in ['\x00', '\x01', '\x02', '\x03', '\x04', '\x05', '\x06', '\x07', '\x08', '\x0B', '\x0C', '\x0E', '\x0F']:
            try:
                test_str = json_str.replace(remove_char, '')
                return json.loads(test_str)
            except:
                continue
        
        # 策略2：尝试修复常见的JSON错误
        fixes = [
            # 修复未闭合的字符串
            lambda s: s + '"' if s.count('"') % 2 == 1 else s,
            # 修复未闭合的对象
            lambda s: s + '}' if s.count('{') > s.count('}') else s,
            # 修复未闭合的数组
            lambda s: s + ']' if s.count('[') > s.count(']') else s,
        ]
        
        for fix in fixes:
            try:
                fixed = fix(json_str)
                return json.loads(fixed)
            except:
                continue
        
        # 策略3：尝试从JSON中间开始解析
        try:
            # 找到第一个完整的JSON对象
            start = json_str.find('{')
            if start >= 0:
                # 使用括号匹配找到完整的JSON
                bracket_count = 0
                for i, char in enumerate(json_str[start:], start):
                    if char == '{':
                        bracket_count += 1
                    elif char == '}':
                        bracket_count -= 1
                        if bracket_count == 0:
                            candidate = json_str[start:i+1]
                            return json.loads(candidate)
        except:
            pass
        
        raise ValueError("容错解析也失败了")
    
    def _clean_json_control_characters(self, json_str: str) -> str:
        """
        深度清理JSON字符串中的无效控制字符
        
        Args:
            json_str: 原始JSON字符串
            
        Returns:
            str: 清理后的JSON字符串
        """
        try:
            logger.info(f"开始清理JSON控制字符，原始长度: {len(json_str)}")
            
            # 方法1：多重编码清理
            cleaned = json_str
            
            # 1.1 UTF-8编码清理
            cleaned = cleaned.encode('utf-8', errors='ignore').decode('utf-8')
            
            # 1.2 ASCII兼容清理
            cleaned = cleaned.encode('ascii', errors='ignore').decode('ascii', errors='ignore')
            
            # 方法2：全面的控制字符清理
            import re
            
            # 2.1 清理所有ASCII控制字符（保留必要的JSON字符）
            # 保留: \n(10), \r(13), \t(9), "(34), \(92)
            # 清理: 其他0-31和127的控制字符
            cleaned = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', cleaned)
            
            # 2.2 清理Unicode控制字符
            cleaned = re.sub(r'[\u0000-\u001F\u007F-\u009F]', '', cleaned)
            
            # 2.3 清理BOM和零宽字符
            cleaned = re.sub(r'[\uFEFF\u200B\u200C\u200D\u2060]', '', cleaned)
            
            # 方法3：针对性字符串内容清理
            def clean_string_content(match):
                content = match.group(1)
                # 更激进的清理策略
                content = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', content)
                content = re.sub(r'[\u0000-\u001F\u007F-\u009F]', '', content)
                return f'"{content}"'
            
            # 匹配双引号内的字符串内容，处理转义字符
            cleaned = re.sub(r'"([^"\\]*(?:\\.[^"\\]*)*)"', clean_string_content, cleaned)
            
            # 方法4：逐字符验证和清理
            valid_chars = []
            for char in cleaned:
                char_code = ord(char)
                # 允许的字符范围
                if (char_code >= 32 and char_code <= 126) or char_code in [9, 10, 13]:  # 可打印字符 + tab/newline/return
                    valid_chars.append(char)
                elif char_code > 127:  # 非ASCII字符（中文等）
                    valid_chars.append(char)
                # 其他控制字符直接丢弃
            
            final_cleaned = ''.join(valid_chars)
            
            logger.info(f"JSON控制字符清理完成，清理后长度: {len(final_cleaned)}")
            logger.info(f"清理掉字符数: {len(json_str) - len(final_cleaned)}")
            
            return final_cleaned
            
        except Exception as e:
            logger.error(f"清理JSON控制字符失败: {e}")
            logger.error(f"错误位置: {e.__traceback__.tb_lineno}")
            return json_str
    
    def _extract_json_object(self, text: str) -> Optional[str]:
        """
        使用括号匹配算法提取完整的JSON对象
        
        Args:
            text: 包含JSON的文本
            
        Returns:
            Optional[str]: 提取到的JSON字符串，如果未找到则返回None
        """
        # 首先尝试从```json代码块中提取
        json_block_match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_block_match:
            potential_json = json_block_match.group(1)
            # 验证这是否是有效的JSON开始
            if potential_json.strip().startswith('{'):
                return self._extract_complete_json_from_start(potential_json.strip())
        
        # 如果没有找到代码块，尝试寻找第一个{
        start_idx = text.find('{')
        if start_idx == -1:
            return None
        
        return self._extract_complete_json_from_start(text[start_idx:])
    
    def _extract_complete_json_from_start(self, text: str) -> Optional[str]:
        """
        从文本开头提取完整的JSON对象
        """
        if not text.startswith('{'):
            return None
        
        bracket_count = 0
        in_string = False
        escape_next = False
        
        for i, char in enumerate(text):
            if escape_next:
                escape_next = False
                continue
                
            if char == '\\':
                escape_next = True
                continue
                
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
                
            if not in_string:
                if char == '{':
                    bracket_count += 1
                elif char == '}':
                    bracket_count -= 1
                    if bracket_count == 0:
                        return text[:i+1]
        
        # 如果没有找到完整的JSON，返回None
        return None
    
    def _try_repair_incomplete_json(self, json_text: str) -> Optional[str]:
        """
        尝试修复不完整的JSON
        """
        if not json_text.strip():
            return None
        
        json_text = json_text.strip()
        
        # 如果不是以{开始，尝试找到第一个{
        if not json_text.startswith('{'):
            start_idx = json_text.find('{')
            if start_idx == -1:
                return None
            json_text = json_text[start_idx:]
        
        # 尝试直接解析
        try:
            json.loads(json_text)
            return json_text
        except json.JSONDecodeError:
            pass
        
        # 策略1: 智能括号匹配 - 找到第一个完整JSON对象
        bracket_count = 0
        in_string = False
        escape_next = False
        
        for i, char in enumerate(json_text):
            if escape_next:
                escape_next = False
                continue
                
            if char == '\\':
                escape_next = True
                continue
                
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
                
            if not in_string:
                if char == '{':
                    bracket_count += 1
                elif char == '}':
                    bracket_count -= 1
                    if bracket_count == 0:
                        potential_json = json_text[:i+1]
                        try:
                            json.loads(potential_json)
                            logger.info(f"修复策略1成功：智能括号匹配，截取到位置{i}")
                            return potential_json
                        except:
                            continue
        
        # 策略2: 按行逆向移除非JSON内容
        lines = json_text.split('\n')
        for i in range(len(lines) - 1, -1, -1):
            test_json = '\n'.join(lines[:i+1]).strip()
            if test_json.endswith('}'):
                try:
                    json.loads(test_json)
                    logger.info(f"修复策略2成功：移除了{len(lines) - i - 1}行额外内容")
                    return test_json
                except:
                    continue
        
        # 策略3: 查找最后一个有效的}位置
        for i in range(len(json_text) - 1, -1, -1):
            if json_text[i] == '}':
                potential_json = json_text[:i+1]
                try:
                    json.loads(potential_json)
                    logger.info(f"修复策略3成功：找到最后有效}}位置{i}")
                    return potential_json
                except:
                    continue
        
        # 策略4: 尝试补全缺失的括号
        open_brackets = json_text.count('{') - json_text.count('}')
        if open_brackets > 0:
            test_json = json_text + '}' * open_brackets
            try:
                json.loads(test_json)
                logger.info(f"修复策略4成功：添加了{open_brackets}个右括号")
                return test_json
            except:
                pass
        
        # 策略5: 使用正则表达式查找第一个完整的JSON块
        import re
        # 查找从第一个{到第一个看起来像JSON结束的位置
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.finditer(json_pattern, json_text, re.DOTALL)
        for match in matches:
            potential_json = match.group(0)
            try:
                json.loads(potential_json)
                logger.info(f"修复策略5成功：正则表达式匹配")
                return potential_json
            except:
                continue
        
        logger.warning("所有JSON修复策略都失败了")
        return None
    
    def _process_explanation_format(self, result_data: dict) -> None:
        """
        处理explanation字段格式，将字典格式转换为字符串格式
        """
        try:
            for result in result_data.get('results', []):
                explanation = result.get('explanation')
                if isinstance(explanation, dict):
                    # 将字典格式的explanation转换为格式化字符串
                    formatted_explanation = self._format_structured_explanation(explanation)
                    result['explanation'] = formatted_explanation
                    logger.info(f"题号{result.get('question_number')}：转换了结构化explanation")
        except Exception as e:
            logger.error(f"处理explanation格式时出错: {e}")
    
    def _format_structured_explanation(self, explanation_dict: dict) -> str:
        """
        将结构化的explanation字典转换为格式化字符串
        """
        try:
            parts = []
            
            # 按照期望的顺序组织内容
            order = ['原文定位', '解题思路', '错误分析', '技巧提醒']
            
            for key in order:
                if key in explanation_dict:
                    content = explanation_dict[key]
                    parts.append(f"【{key}】{content}")
            
            # 如果有其他字段，也添加进去
            for key, value in explanation_dict.items():
                if key not in order:
                    parts.append(f"【{key}】{value}")
            
            return '\n'.join(parts)
            
        except Exception as e:
            logger.error(f"格式化结构化explanation时出错: {e}")
            return str(explanation_dict)
    
    def _create_fallback_response(
        self,
        questions: List[DSEQuestion],
        user_answers: List[UserAnswer],
        time_spent: float
    ) -> AITeacherResponse:
        """
        创建降级响应
        
        当AI服务不可用时，提供基础的批改功能，
        确保系统的可用性和用户体验。
        
        Args:
            questions: 题目列表
            user_answers: 用户答案
            time_spent: 答题用时
            
        Returns:
            AITeacherResponse: 降级的批改结果
        """
        logger.warning("使用降级批改模式")
        
        answer_map = {ans.question_id: ans for ans in user_answers}
        results = []
        correct_count = 0
        
        # 为每个子题创建单独的结果
        sub_question_counter = 1
        for question in questions:
            user_answer = answer_map.get(question.id)
            
            if question.type == "fill-in-blank" and question.subQuestions:
                # 填空题：为每个子题创建单独结果
                for i, sub_question in enumerate(question.subQuestions):
                    user_sub_answer = ""
                    correct_sub_answer = sub_question.correctAnswer
                    
                    # 提取用户对该子题的答案 - 支持多种格式
                    if user_answer:
                        # 优先使用fillInAnswers（前端格式）
                        if hasattr(user_answer, 'fillInAnswers') and user_answer.fillInAnswers:
                            user_sub_answer = user_answer.fillInAnswers.get(sub_question.id, "")
                        # 备用fill_in_answers（后端格式）
                        elif hasattr(user_answer, 'fill_in_answers') and user_answer.fill_in_answers:
                            user_sub_answer = user_answer.fill_in_answers.get(sub_question.id, "")
                        # 兼容字典访问方式
                        elif isinstance(user_answer, dict):
                            fill_answers = user_answer.get('fillInAnswers') or user_answer.get('fill_in_answers') or {}
                            user_sub_answer = fill_answers.get(sub_question.id, "")
                        # 如果是字符串形式的答案，按逗号分割（兼容旧格式）
                        elif hasattr(user_answer, 'selected_option') and user_answer.selected_option:
                            answers = user_answer.selected_option.split(',')
                            if i < len(answers):
                                user_sub_answer = answers[i].strip()
                    
                    # 检查填空题答案是否有效
                    if user_sub_answer and user_sub_answer.strip() and user_sub_answer != "undefined" and user_sub_answer != "null":
                        clean_user_answer = user_sub_answer.strip()
                        # 判断子题是否正确
                        is_sub_correct = clean_user_answer.lower() == correct_sub_answer.lower().strip()
                        if is_sub_correct:
                            correct_count += 1
                    else:
                        clean_user_answer = "未作答"
                        is_sub_correct = False
                    
                    result = QuestionResult(
                        question_number=sub_question_counter,
                        is_correct=is_sub_correct,
                        user_answer=clean_user_answer,
                        correct_answer=correct_sub_answer,
                        explanation=f"第{question.questionNumber}题第{i+1}小题：{sub_question.questionText}",
                        skill_analysis=f"该题考查{self._get_skill_description(question.skillType.value)}能力",
                        reference_text=None
                    )
                    results.append(result)
                    sub_question_counter += 1
            
            elif question.type == "timeline-sequencing" and question.correctAnswers:
                # 时序题：为每个位置创建单独结果
                user_timeline_answers = {}
                if user_answer:
                    # 优先使用timelineAnswers（前端格式）
                    if hasattr(user_answer, 'timelineAnswers') and user_answer.timelineAnswers:
                        user_timeline_answers = user_answer.timelineAnswers or {}
                    # 备用timeline_answers（后端格式）
                    elif hasattr(user_answer, 'timeline_answers') and user_answer.timeline_answers:
                        user_timeline_answers = user_answer.timeline_answers or {}
                    # 兼容字典访问方式
                    elif isinstance(user_answer, dict):
                        user_timeline_answers = user_answer.get('timelineAnswers') or user_answer.get('timeline_answers') or {}
                    # 解析选项格式 "A, B, C"（兼容旧格式）
                    elif hasattr(user_answer, 'selected_option') and user_answer.selected_option:
                        answers = user_answer.selected_option.split(',')
                        positions = ['i', 'ii', 'iii']
                        for idx, ans in enumerate(answers[:3]):
                            if idx < len(positions):
                                user_timeline_answers[positions[idx]] = ans.strip()
                
                for position, correct_answer in question.correctAnswers.items():
                    raw_pos_answer = user_timeline_answers.get(position, "")
                    
                    # 检查时序题答案是否有效
                    if raw_pos_answer and raw_pos_answer.strip() and raw_pos_answer != "undefined" and raw_pos_answer != "null":
                        clean_pos_answer = raw_pos_answer.strip()
                        is_pos_correct = clean_pos_answer.upper() == correct_answer.upper().strip()
                        if is_pos_correct:
                            correct_count += 1
                    else:
                        clean_pos_answer = "未作答"
                        is_pos_correct = False
                    
                    result = QuestionResult(
                        question_number=sub_question_counter,
                        is_correct=is_pos_correct,
                        user_answer=clean_pos_answer,
                        correct_answer=correct_answer,
                        explanation=f"第{question.questionNumber}题位置({position})：时序排列",
                        skill_analysis=f"该题考查{self._get_skill_description(question.skillType.value)}能力",
                        reference_text=None
                    )
                    results.append(result)
                    sub_question_counter += 1
            
            else:
                # 单选题等其他类型
                user_answer_text = self._format_user_answer(question, user_answer)
                correct_answer_text = self._format_correct_answer(question)
                is_correct = self._basic_answer_check(question, user_answer)
                if is_correct:
                    correct_count += 1
                
                result = QuestionResult(
                    question_number=sub_question_counter,
                    is_correct=is_correct,
                    user_answer=user_answer_text,
                    correct_answer=correct_answer_text,
                    explanation=f"第{question.questionNumber}题：{question.questionText[:50]}...",
                    skill_analysis=f"该题考查{self._get_skill_description(question.skillType.value)}能力",
                    reference_text=None
                )
                results.append(result)
                sub_question_counter += 1
        
        # 计算总的子题数量
        total_sub_questions = len(results)
        final_score = correct_count / total_sub_questions if total_sub_questions > 0 else 0
        
        return AITeacherResponse(
            results=results,
            final_score=final_score,
            correct_count=correct_count,
            total_questions=total_sub_questions,
            ability_analysis="AI服务暂时不可用，无法提供详细的能力分析。请稍后重试。",
            strengths=["基础理解"],
            weaknesses=["需要更多练习"],
            recommendations=["继续练习阅读理解", "注意题目要求", "提高答题准确性"],
            time_spent=int(time_spent)
        )
    
    def _basic_answer_check(self, question: DSEQuestion, user_answer: Optional[UserAnswer]) -> bool:
        """基础答案检查（降级模式使用）"""
        if not user_answer:
            return False
        
        if question.type == QuestionType.MULTIPLE_CHOICE:
            # 多种方式获取选择题答案，并检查有效性
            selected = None
            if hasattr(user_answer, 'selected_option'):
                selected = user_answer.selected_option
            elif hasattr(user_answer, 'selectedOption'):
                selected = user_answer.selectedOption
            elif isinstance(user_answer, dict):
                selected = user_answer.get('selected_option') or user_answer.get('selectedOption')
            
            # 检查答案是否有效
            if not selected or not selected.strip() or selected == "undefined" or selected == "null":
                return False
                
            return selected.strip() == question.correctAnswer
        
        elif question.type == QuestionType.FILL_IN_BLANK and question.subQuestions:
            # 获取填空题答案
            fill_answers = {}
            if hasattr(user_answer, 'fillInAnswers') and user_answer.fillInAnswers:
                fill_answers = user_answer.fillInAnswers
            elif hasattr(user_answer, 'fill_in_answers') and user_answer.fill_in_answers:
                fill_answers = user_answer.fill_in_answers
            elif isinstance(user_answer, dict):
                fill_answers = user_answer.get('fillInAnswers') or user_answer.get('fill_in_answers') or {}
            
            return all(
                fill_answers and
                fill_answers.get(sub_q.id, "").lower().strip() == 
                sub_q.correctAnswer.lower().strip()
                for sub_q in question.subQuestions
            )
        
        elif question.type == QuestionType.TIMELINE_SEQUENCING and question.correctAnswers:
            # 获取时序题答案
            timeline_answers = {}
            if hasattr(user_answer, 'timelineAnswers') and user_answer.timelineAnswers:
                timeline_answers = user_answer.timelineAnswers
            elif hasattr(user_answer, 'timeline_answers') and user_answer.timeline_answers:
                timeline_answers = user_answer.timeline_answers
            elif isinstance(user_answer, dict):
                timeline_answers = user_answer.get('timelineAnswers') or user_answer.get('timeline_answers') or {}
            
            return all(
                timeline_answers and
                timeline_answers.get(pos) == letter
                for pos, letter in question.correctAnswers.items()
            )
        
        return False
    
    def _validate_and_fix_user_answers(self, result_data: Dict[str, Any], context: Dict[str, Any]) -> None:
        """
        验证并修正AI返回的用户答案，确保与实际输入一致
        
        AI模型有时会错误地返回用户答案，这会导致批改结果不准确。
        此方法通过对比实际输入的答案和AI返回的答案来发现并修正这类错误。
        
        Args:
            result_data: AI返回的批改结果数据
            context: 包含实际用户答案的上下文数据
        """
        if 'sub_questions' not in context or 'results' not in result_data:
            logger.warning("缺少必要的数据来验证用户答案")
            return
        
        # 创建实际用户答案的映射
        actual_answers_map = {}
        for sub_q in context['sub_questions']:
            sub_question_number = sub_q['sub_question_number']
            actual_user_answer = sub_q['user_answer']
            actual_answers_map[sub_question_number] = actual_user_answer
        
        # 验证并修正AI返回的用户答案
        fixes_count = 0
        for result in result_data['results']:
            question_number = result.get('question_number')
            ai_returned_answer = result.get('user_answer', '')
            actual_answer = actual_answers_map.get(question_number, '')
            
            # 比较答案（忽略大小写和空格）
            ai_answer_normalized = ai_returned_answer.strip().lower() if ai_returned_answer else ''
            actual_answer_normalized = actual_answer.strip().lower() if actual_answer else ''
            
            if ai_answer_normalized != actual_answer_normalized:
                logger.warning(f"题目{question_number}: 检测到AI返回错误的用户答案")
                logger.warning(f"  AI返回答案: '{ai_returned_answer}'")
                logger.warning(f"  实际用户答案: '{actual_answer}'")
                
                # 修正用户答案
                result['user_answer'] = actual_answer
                fixes_count += 1
                
                # 重新评估正确性
                correct_answer = result.get('correct_answer', '').strip().lower()
                if actual_answer_normalized == correct_answer:
                    if not result.get('is_correct'):
                        logger.info(f"  修正后判断为正确答案")
                        result['is_correct'] = True
                else:
                    if result.get('is_correct'):
                        logger.info(f"  修正后判断为错误答案") 
                        result['is_correct'] = False
                
                # 更新解析说明中的用户答案信息和逻辑判断
                explanation = result.get('explanation', '')
                if explanation:
                    # 1. 替换所有出现的错误用户答案
                    if ai_returned_answer:
                        explanation = explanation.replace(
                            f"你的答案: {ai_returned_answer}",
                            f"你的答案: {actual_answer}"
                        )
                        explanation = explanation.replace(
                            f"用户答案:'{ai_returned_answer}'",
                            f"用户答案:'{actual_answer}'"
                        )
                        explanation = explanation.replace(
                            f"学生答案'{ai_returned_answer}'",
                            f"学生答案'{actual_answer}'"
                        )
                        explanation = explanation.replace(
                            f"學生答案'{ai_returned_answer}'",
                            f"學生答案'{actual_answer}'"
                        )
                    
                    # 2. 修正错误的逻辑判断文本
                    if actual_answer_normalized != correct_answer:
                        # 如果答案错误，需要修正AI在explanation中的错误逻辑判断
                        
                        # 修正包含"完全正确"的错误判断
                        wrong_correct_patterns = [
                            f"學生答案'{ai_returned_answer}'完全正確",
                            f"學生答案'{actual_answer}'完全正確", 
                            f"学生答案'{ai_returned_answer}'完全正确",
                            f"学生答案'{actual_answer}'完全正确",
                            f"答案'{ai_returned_answer}'完全正确", 
                            f"答案'{actual_answer}'完全正确",
                            "完全正確，準確搵到咗原文中",
                            "完全正确，准确地从原文中找到了",
                            "準確搵到咗原文中與restrict對應嘅同義詞"
                        ]
                        
                        for pattern in wrong_correct_patterns:
                            if pattern in explanation:
                                explanation = explanation.replace(
                                    pattern,
                                    f"學生答案'{actual_answer}'係錯誤嘅。正確答案應該係'{result.get('correct_answer', '')}'"
                                )
                        
                        # 修正【錯誤分析】部分 - 处理粤语版本
                        import re
                        
                        # 查找并替换错误的分析内容
                        error_analysis_patterns = [
                            r'【錯誤分析】學生答案[^【]*完全正確[^【]*',
                            r'【错误分析】学生答案[^【]*完全正确[^【]*',
                            r'學生答案[^。]*完全正確[^。]*。',
                            r'学生答案[^。]*完全正确[^。]*。'
                        ]
                        
                        for pattern in error_analysis_patterns:
                            if re.search(pattern, explanation):
                                explanation = re.sub(
                                    pattern,
                                    f"【錯誤分析】🔍 **學生答案分析**：學生填咗'{actual_answer}'，呢個答案係錯誤嘅。正確答案應該係'{result.get('correct_answer', '')}'。學生可能對原文中嘅關鍵詞彙理解有偏差，或者係審題唔夠仔細。",
                                    explanation
                                )
                        
                        # 如果仍然包含错误的正面评价，进行通用替换
                        positive_phrases = [
                            "準確咁",
                            "準確地",  
                            "正確地",
                            "成功地",
                            "準確搵到",
                            "正確搵到"
                        ]
                        
                        for phrase in positive_phrases:
                            if phrase in explanation and "錯誤" not in explanation[:explanation.find(phrase)+50]:
                                explanation = explanation.replace(phrase, "未能")
                    
                    result['explanation'] = explanation
                
                logger.info(f"  已修正用户答案为: '{actual_answer}'")
                logger.info(f"  已修正讲解内容中的错误逻辑判断")
            else:
                logger.info(f"题目{question_number}: 用户答案一致 - '{actual_answer}'")
        
        if fixes_count > 0:
            logger.warning(f"修正了{fixes_count}个用户答案错误")
        else:
            logger.info("所有用户答案都正确匹配")
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.client.aclose()
    
    def _validate_and_fix_skill_analysis(self, ai_response: 'AITeacherResponse', context: Dict[str, Any]) -> None:
        """
        验证和修正AI技能分析数据（混合智能模式）
        
        策略：
        1. 保留AI的创意分析和技能分类  
        2. 只修正明显的统计计算错误
        3. 支持AI生成的动态技能分类
        4. 保持AI的智能分析能力
        """
        try:
            # 从context获取子题目数据，按技能分类统计
            sub_questions = context.get('sub_questions', [])
            actual_skill_stats = {}
            
            # 统计每个技能的实际表现
            for sub_q in sub_questions:
                skill_type = sub_q.get('skill_type', 'unknown')
                if skill_type not in actual_skill_stats:
                    actual_skill_stats[skill_type] = {
                        'total': 0,
                        'correct': 0,
                        'questions': []
                    }
                
                actual_skill_stats[skill_type]['total'] += 1
                actual_skill_stats[skill_type]['questions'].append(sub_q)
                
                # 检查是否答对
                question_num = sub_q.get('sub_question_number')
                for result in ai_response.results:
                    if result.question_number == question_num and result.is_correct:
                        actual_skill_stats[skill_type]['correct'] += 1
                        break
            
            logger.info(f"实际技能统计: {actual_skill_stats}")
            
            # 技能名称映射（支持AI的创新分类）
            skill_name_map = {
                'vocabulary': '詞彙理解',
                'detail': '細節理解', 
                'inference': '推理判斷',
                'main-idea': '主旨大意',
                'structure': '文章結構',
                'sequencing': '時序邏輯',
                'cultural-context': '文化語境',
                'critical-thinking': '批判思維',
                'emotional-tone': '情感語調',
                'scientific-reasoning': '科學推理',
                'narrative-structure': '敘事結構'
                    }
            
            # 检查AI返回的技能分析数据
            ai_skill_breakdown = ai_response.skill_breakdown or []
            need_correction = False
            corrected_skill_breakdown = []
            
            # 优先保留AI的分析，只修正统计错误
            for ai_skill in ai_skill_breakdown:
                # 处理Pydantic对象或字典
                if hasattr(ai_skill, 'skill_name'):
                    skill_name = ai_skill.skill_name
                    ai_mastery = ai_skill.mastery_level
                    ai_correct = ai_skill.correct_count
                    ai_total = ai_skill.total_count
                    ai_description = getattr(ai_skill, 'performance_description', '')
                else:
                    skill_name = ai_skill.get('skill_name', '')
                    ai_mastery = ai_skill.get('mastery_level', 0)
                    ai_correct = ai_skill.get('correct_count', 0)
                    ai_total = ai_skill.get('total_count', 0)
                    ai_description = ai_skill.get('performance_description', '')
                
                # 寻找对应的实际数据（通过技能名称反向映射）
                corresponding_skill_type = None
                for skill_type, mapped_name in skill_name_map.items():
                    if mapped_name == skill_name:
                        corresponding_skill_type = skill_type
                        break
                
                # 如果找到对应的技能类型，检查统计数据是否正确
                if corresponding_skill_type and corresponding_skill_type in actual_skill_stats:
                    actual_stats = actual_skill_stats[corresponding_skill_type]
                    actual_correct = actual_stats['correct']
                    actual_total = actual_stats['total']
                    actual_mastery = actual_correct / actual_total if actual_total > 0 else 0
                    
                    # 检查是否需要修正统计数据
                    if ai_correct != actual_correct or ai_total != actual_total or abs(ai_mastery - actual_mastery) > 0.05:
                        logger.warning(f"技能分析統計錯誤 - {skill_name}: AI({ai_correct}/{ai_total}={ai_mastery:.2f}) vs 實際({actual_correct}/{actual_total}={actual_mastery:.2f})")
                        need_correction = True
            
                        # 创建修正后的技能数据，保留AI的描述和分析
                        corrected_skill = SkillMastery(
                            skill_name=skill_name,
                            mastery_level=actual_mastery,
                            correct_count=actual_correct,
                            total_count=actual_total,
                            performance_description=ai_description or self._generate_performance_description(skill_name, actual_mastery, actual_correct, actual_total)
                        )
                        corrected_skill_breakdown.append(corrected_skill)
                    else:
                        # 统计数据正确，保留AI的原始分析
                        if hasattr(ai_skill, 'skill_name'):
                            corrected_skill_breakdown.append(ai_skill)
                        else:
                            # 如果是字典，转换为Pydantic对象
                            corrected_skill = SkillMastery(
                                skill_name=skill_name,
                                mastery_level=ai_mastery,
                                correct_count=ai_correct,
                                total_count=ai_total,
                                performance_description=ai_description or self._generate_performance_description(skill_name, ai_mastery, ai_correct, ai_total)
                            )
                            corrected_skill_breakdown.append(corrected_skill)
                else:
                    # AI创造了新的技能分类，保留但记录日志
                    logger.info(f"AI創新技能分類: {skill_name}")
                    if hasattr(ai_skill, 'skill_name'):
                        corrected_skill_breakdown.append(ai_skill)
                    else:
                        corrected_skill = SkillMastery(
                            skill_name=skill_name,
                            mastery_level=ai_mastery,
                            correct_count=ai_correct,
                            total_count=ai_total,
                            performance_description=ai_description or self._generate_performance_description(skill_name, ai_mastery, ai_correct, ai_total)
                        )
                        corrected_skill_breakdown.append(corrected_skill)
            
            # 如果需要修正或AI没有返回技能分析
            if need_correction:
                logger.warning("檢測到AI技能分析統計錯誤，使用混合智能修正模式")
                
                # 重新计算优势和劣势（基于修正后的数据）
                corrected_strengths = []
                corrected_weaknesses = []
                corrected_strengths_detailed = []
                corrected_weaknesses_detailed = []
                
                for skill in corrected_skill_breakdown:
                    if skill.mastery_level >= 0.7:
                        corrected_strengths.append(skill.skill_name)
                        strength_detail = StrengthDetail(
                            skill_name=skill.skill_name,
                            mastery_level=skill.mastery_level,
                            description=f"你在{skill.skill_name}方面表現出色，掌握度達到{skill.mastery_level*100:.0f}%。{skill.performance_description}",
                            evidence=[f"在{skill.skill_name}相關題目中答對{skill.correct_count}/{skill.total_count}題"]
                        )
                        corrected_strengths_detailed.append(strength_detail)
                    elif skill.mastery_level < 0.6:
                        corrected_weaknesses.append(skill.skill_name)
                        weakness_detail = WeaknessDetail(
                            skill_name=skill.skill_name,
                            mastery_level=skill.mastery_level,
                            description=f"{skill.skill_name}是你目前需要加強的方面，掌握度為{skill.mastery_level*100:.0f}%。{skill.performance_description}",
                            improvement_suggestions=self._generate_improvement_suggestions(skill.skill_name),
                            practice_focus=self._generate_practice_focus(skill.skill_name)
                        )
                        corrected_weaknesses_detailed.append(weakness_detail)
                
                # 更新AI响应，保留其他AI分析内容
                ai_response.skill_breakdown = corrected_skill_breakdown
                ai_response.strengths_detailed = corrected_strengths_detailed or ai_response.strengths_detailed
                ai_response.weaknesses_detailed = corrected_weaknesses_detailed or ai_response.weaknesses_detailed
                ai_response.strengths = corrected_strengths or ai_response.strengths
                ai_response.weaknesses = corrected_weaknesses or ai_response.weaknesses
                
                logger.info(f"混合智能修正完成:")
                for skill in corrected_skill_breakdown:
                    logger.info(f"  {skill.skill_name}: {skill.mastery_level:.2f} ({skill.correct_count}/{skill.total_count})")
            elif not ai_skill_breakdown:
                # AI没有返回技能分析数据，使用备用方案
                logger.warning("AI未返回技能分析數據，使用基礎智能分析")
                self._generate_fallback_skill_analysis(ai_response, actual_skill_stats, skill_name_map)
            else:
                logger.info("AI技能分析數據準確，保留原始智能分析")
                # 确保数据格式正确
                if corrected_skill_breakdown:
                    ai_response.skill_breakdown = corrected_skill_breakdown
                
        except Exception as e:
            logger.error(f"技能分析驗證失敗: {e}")
            logger.warning("強制使用基於實際答題結果的修正數據")
            
            # 最后的备用方案：使用完全基于实际数据的分析
            try:
                # 生成基础的技能分析作为备用
                fallback_breakdown = []
                fallback_strengths = []
                fallback_weaknesses = []
                
                for skill_type, stats in actual_skill_stats.items():
                    skill_name = skill_name_map.get(skill_type, skill_type)
                    mastery_level = stats['correct'] / stats['total'] if stats['total'] > 0 else 0
                    
                    skill_item = SkillMastery(
                        skill_name=skill_name,
                        mastery_level=mastery_level,
                        correct_count=stats['correct'],
                        total_count=stats['total'],
                        performance_description=self._generate_performance_description(skill_name, mastery_level, stats['correct'], stats['total'])
                    )
                    fallback_breakdown.append(skill_item)
                    
                    if mastery_level >= 0.7:
                        fallback_strengths.append(skill_name)
                    elif mastery_level < 0.6:
                        fallback_weaknesses.append(skill_name)
                
                ai_response.skill_breakdown = fallback_breakdown
                ai_response.strengths = fallback_strengths
                ai_response.weaknesses = fallback_weaknesses
                
                logger.info(f"備用方案修正完成:")
                for skill in fallback_breakdown:
                    logger.info(f"  {skill.skill_name}: {skill.mastery_level:.2f} ({skill.correct_count}/{skill.total_count})")
            except Exception as force_error:
                logger.error(f"備用方案也失敗: {force_error}")
    
    def _generate_performance_description(self, skill_name: str, mastery_level: float, correct: int, total: int) -> str:
        """生成表現描述"""
        if mastery_level >= 0.9:
            return f"在{skill_name}方面表現卓越，掌握程度極高，能夠準確處理相關題目。"
        elif mastery_level >= 0.7:
            return f"在{skill_name}方面表現良好，掌握程度較高，大部分相關題目都能正確處理。"
        elif mastery_level >= 0.5:
            return f"在{skill_name}方面掌握程度一般，有進步空間，需要加強練習。"
        else:
            return f"在{skill_name}方面需要重點提升，掌握程度較低，建議針對性加強練習。"
    
    def _generate_strength_description(self, skill_name: str, mastery_level: float) -> str:
        """生成優勢描述"""
        descriptions = {
            '詞彙理解': f"你在詞彙理解方面表現出色，掌握程度達到{int(mastery_level*100)}%。能夠準確理解詞彙在不同語境下的含義，對同義詞替換有良好的敏感度。",
            '細節理解': f"你在細節理解方面表現良好，掌握程度達到{int(mastery_level*100)}%。能夠準確定位和提取文章中的關鍵信息。",
            '推理判斷': f"你在推理判斷方面表現出色，掌握程度達到{int(mastery_level*100)}%。能夠根據文章內容進行有效的邏輯推理。",
            '主旨大意': f"你在主旨大意理解方面表現良好，掌握程度達到{int(mastery_level*100)}%。能夠準確把握文章的中心思想。",
            '文章結構': f"你在文章結構理解方面表現出色，掌握程度達到{int(mastery_level*100)}%。能夠清楚理解文章的組織方式。",
            '時序邏輯': f"你在時序邏輯方面表現優異，掌握程度達到{int(mastery_level*100)}%。能夠準確判斷事件的先後順序和時間關係。"
        }
        return descriptions.get(skill_name, f"你在{skill_name}方面表現良好，掌握程度達到{int(mastery_level*100)}%。")
    
    def _generate_weakness_description(self, skill_name: str, mastery_level: float) -> str:
        """生成劣勢描述"""
        descriptions = {
            '詞彙理解': f"詞彙理解是你目前需要加強的方面，掌握程度僅{int(mastery_level*100)}%。在理解多義詞和同義詞替換方面存在困難。",
            '細節理解': f"細節理解需要進一步提升，掌握程度僅{int(mastery_level*100)}%。在定位和提取關鍵信息方面有待改善。",
            '推理判斷': f"推理判斷能力有待提升，掌握程度僅{int(mastery_level*100)}%。在根據上下文推斷隱含意思方面存在困難。",
            '主旨大意': f"主旨大意理解需要加強，掌握程度僅{int(mastery_level*100)}%。在把握文章整體思路方面有困難。",
            '文章結構': f"文章結構理解需要提升，掌握程度僅{int(mastery_level*100)}%。在理解文章組織方式方面存在困難。",
            '時序邏輯': f"時序邏輯理解是你目前的主要弱項，掌握程度僅{int(mastery_level*100)}%。在理解事件先後順序方面存在較大困難。"
        }
        return descriptions.get(skill_name, f"{skill_name}需要進一步提升，掌握程度僅{int(mastery_level*100)}%。")
    
    def _generate_evidence_for_skill(self, skill_name: str, questions: list, results: list, is_strength: bool) -> list:
        """為技能生成支撐證據"""
        evidence = []
        for q in questions[:3]:  # 最多3個證據
            question_num = q.get('sub_question_number')
            for result in results:
                if result.question_number == question_num:
                    if (is_strength and result.is_correct) or (not is_strength and not result.is_correct):
                        if skill_name == '詞彙理解':
                            evidence.append(f"正確處理了詞彙相關題目：{result.user_answer}")
                        elif skill_name == '時序邏輯':
                            evidence.append(f"準確判斷了事件順序：選擇{result.user_answer}")
                        else:
                            evidence.append(f"正確回答了{skill_name}相關題目")
                    break
        return evidence or [f"在{skill_name}相關題目中表現良好"]
    
    def _generate_improvement_suggestions(self, skill_name: str) -> list:
        """生成改進建議"""
        suggestions = {
            '詞彙理解': [
                "多閱讀不同類型的文章，積累詞彙量",
                "學習詞彙在不同語境下的含義",
                "練習同義詞替換和詞彙辨析題目",
                "使用詞典查找多義詞的不同用法"
            ],
            '細節理解': [
                "練習快速定位關鍵信息的技巧",
                "學會識別題目中的關鍵詞",
                "提高對數字、時間等具體信息的敏感度",
                "多做細節理解專項練習"
            ],
            '時序邏輯': [
                "閱讀時主動標記時間標誌詞",
                "練習畫時間線，將事件按順序排列", 
                "多做時序排列的專項練習",
                "學會識別因果關係和邏輯順序"
            ],
            '推理判斷': [
                "多練習根據上下文推斷題目",
                "學會識別文章中的邏輯關係",
                "提高對作者意圖的理解能力",
                "練習從隱含信息中得出結論"
            ]
        }
        return suggestions.get(skill_name, [f"多練習{skill_name}相關題型", "加強基礎訓練", "尋求專業指導"])
    
    def _generate_practice_focus(self, skill_name: str) -> str:
        """生成練習重點"""
        focus = {
            '詞彙理解': "重點練習詞彙辨析和同義詞替換題型，建議每天花15分鐘積累新詞彙。",
            '細節理解': "重點練習信息定位題，建議每天做2-3道細節理解題保持敏感度。",
            '時序邏輯': "重點練習時序排列題型，建議每天花15分鐘專門練習事件排序。",
            '推理判斷': "重點練習推理題型，建議每天做1-2道推斷題提高邏輯思維。"
        }
        return focus.get(skill_name, f"重點練習{skill_name}相關題型，循序漸進提高能力。")
    
    def _generate_ability_analysis(self, strengths: list, weaknesses: list, final_score: float) -> str:
        """生成能力分析概要"""
        if not strengths and not weaknesses:
            return "整體表現平均，各項技能發展較為均衡，建議繼續保持練習。"
        
        analysis = ""
        if strengths:
            analysis += f"學生在{'/'.join(strengths)}方面表現出色，"
        
        if weaknesses:
            if analysis:
                analysis += f"但在{'/'.join(weaknesses)}方面需要加強練習。"
            else:
                analysis += f"學生在{'/'.join(weaknesses)}方面需要重點提升。"
        else:
            analysis += "各項技能掌握良好。"
        
        if final_score >= 0.8:
            analysis += "整體答題思路清晰，表現優異。"
        elif final_score >= 0.6:
            analysis += "整體表現良好，繼續努力可以取得更好成績。"
        else:
            analysis += "需要加強基礎練習，提高整體理解能力。"
            
        return analysis
    
    def _generate_fallback_skill_analysis(self, ai_response: 'AITeacherResponse', actual_skill_stats: dict, skill_name_map: dict) -> None:
        """
        生成备用技能分析（当AI未返回技能分析数据时使用）
        """
        try:
            fallback_breakdown = []
            fallback_strengths = []
            fallback_weaknesses = []
            fallback_strengths_detailed = []
            fallback_weaknesses_detailed = []
            
            for skill_type, stats in actual_skill_stats.items():
                skill_name = skill_name_map.get(skill_type, skill_type)
                mastery_level = stats['correct'] / stats['total'] if stats['total'] > 0 else 0
                
                skill_item = SkillMastery(
                    skill_name=skill_name,
                    mastery_level=mastery_level,
                    correct_count=stats['correct'],
                    total_count=stats['total'],
                    performance_description=self._generate_performance_description(skill_name, mastery_level, stats['correct'], stats['total'])
                )
                fallback_breakdown.append(skill_item)
                
                # 生成优势和劣势分析
                if mastery_level >= 0.7:
                    fallback_strengths.append(skill_name)
                    strength_detail = StrengthDetail(
                        skill_name=skill_name,
                        mastery_level=mastery_level,
                        description=self._generate_strength_description(skill_name, mastery_level),
                        evidence=self._generate_evidence_for_skill(skill_name, stats['questions'], ai_response.results, True)
                    )
                    fallback_strengths_detailed.append(strength_detail)
                elif mastery_level < 0.6:
                    fallback_weaknesses.append(skill_name)
                    weakness_detail = WeaknessDetail(
                        skill_name=skill_name,
                        mastery_level=mastery_level,
                        description=self._generate_weakness_description(skill_name, mastery_level),
                        improvement_suggestions=self._generate_improvement_suggestions(skill_name),
                        practice_focus=self._generate_practice_focus(skill_name)
                    )
                    fallback_weaknesses_detailed.append(weakness_detail)
            
            # 更新AI响应
            ai_response.skill_breakdown = fallback_breakdown
            ai_response.strengths = fallback_strengths
            ai_response.weaknesses = fallback_weaknesses
            ai_response.strengths_detailed = fallback_strengths_detailed
            ai_response.weaknesses_detailed = fallback_weaknesses_detailed
            
            # 重新生成能力分析概要
            ai_response.ability_analysis = self._generate_ability_analysis(fallback_strengths, fallback_weaknesses, ai_response.final_score)
            
            logger.info(f"備用技能分析生成完成:")
            for skill in fallback_breakdown:
                logger.info(f"  {skill.skill_name}: {skill.mastery_level:.2f} ({skill.correct_count}/{skill.total_count})")
                
        except Exception as e:
            logger.error(f"生成備用技能分析失敗: {e}")