"""
DSE英文阅读理解API路由

本模块实现DSE Demo系统的核心API接口，包括：
- 题目数据获取
- 答案提交处理
- 批改结果查询

设计原则：
- RESTful设计：遵循REST API设计规范
- 异步处理：支持高并发请求
- 错误处理：完善的异常处理和错误返回
- 文档完善：自动生成API文档
- 类型安全：使用Pydantic进行数据验证
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import Dict, Any
import logging
import asyncio
import json
from datetime import datetime
import aiofiles

from ..models.dse_models import (
    DemoQuestionsResponse,
    SubmitAnswersRequest,
    SubmissionResponse,
    GradingStatusResponse,
    AITeacherResponse,
    ErrorResponse,
    DSEPassage,
    DSEQuestion,
    QuestionType,
    SkillType
)
from ..services.ai_teacher import AITeacherService
from ..core.config import get_settings

# 创建路由器
router = APIRouter(
    prefix="/api/dse",
    tags=["DSE"],
    responses={
        404: {"description": "资源未找到"},
        500: {"description": "服务器内部错误"}
    }
)

# 日志记录器
logger = logging.getLogger(__name__)

# 全局存储（生产环境应使用Redis或数据库）
submission_store: Dict[str, Dict[str, Any]] = {}

# 获取配置
settings = get_settings()


async def load_demo_data() -> Dict[str, Any]:
    """
    加载Demo数据
    
    从data目录读取题目和文章数据，并转换为API模型格式
    
    Returns:
        Dict[str, Any]: 包含文章和题目的数据字典
        
    Raises:
        HTTPException: 数据加载失败时抛出
    """
    try:
        # 获取数据目录的绝对路径
        import os
        from pathlib import Path
        
        # 获取项目根目录（backend的父目录）
        # __file__ 是 backend/app/routes/dse.py
        # parent: backend/app/routes
        # parent.parent: backend/app  
        # parent.parent.parent: backend
        # parent.parent.parent.parent: HKDSE_AI (项目根目录)
        project_root = Path(__file__).parent.parent.parent.parent
        data_dir = project_root / "data"
        
        logger.info(f"数据目录路径: {data_dir}")
        logger.info(f"数据目录是否存在: {data_dir.exists()}")
        
        # 读取文章数据
        article_file = data_dir / "article.json"
        async with aiofiles.open(article_file, "r", encoding="utf-8") as f:
            article_data = json.loads(await f.read())
        
        # 读取题目数据
        questions_file = data_dir / "questions.json"
        async with aiofiles.open(questions_file, "r", encoding="utf-8") as f:
            questions_data = json.loads(await f.read())
        
        # 读取答案数据
        answers_file = data_dir / "answers.json"
        async with aiofiles.open(answers_file, "r", encoding="utf-8") as f:
            answers_data = json.loads(await f.read())
        
        # 构建完整的HTML内容
        html_content = "<div class='passage-content'>"
        for para in article_data["paragraphs"]:
            if para["type"] == "paragraph":
                html_content += f'<p id="{para["id"]}">{para["content"]}</p>'
            elif para["type"] == "heading":
                level = para["level"]
                html_content += f'<h{level} id="{para["id"]}">{para["content"]}</h{level}>'
        html_content += "</div>"
        
        # 构建文章模型
        passage = DSEPassage(
            id="dse-2023-flash-fiction",
            title=article_data["title"],
            content=html_content,
            wordCount=article_data["wordCount"],
            difficulty=article_data["difficulty"],
            year=2023,
            paper=article_data["reference"]
        )
        
        # 处理题目数据，添加解析信息
        questions = []
        for q_data in questions_data:
            # 从答案数据中获取解析（answers_data是对象，不是数组）
            question_id = q_data["id"]
            answer_info = answers_data.get(question_id, {})
            
            # 提取解析信息，处理不同的数据格式
            explanation = ""
            if answer_info:
                if "explanation" in answer_info:
                    explanation = answer_info["explanation"]
                else:
                    # 如果没有直接的explanation字段，可能需要从子问题中提取
                    explanations = []
                    for key, value in answer_info.items():
                        if isinstance(value, dict) and "explanation" in value:
                            explanations.append(value["explanation"])
                    if explanations:
                        explanation = " | ".join(explanations)
            
            question = DSEQuestion(
                id=q_data["id"],
                questionNumber=q_data["questionNumber"],
                questionText=q_data["questionText"],
                type=QuestionType(q_data["type"]),
                options=q_data.get("options"),
                correctAnswer=q_data.get("correctAnswer"),
                subQuestions=q_data.get("subQuestions"),
                timelineEvents=q_data.get("timelineEvents"),
                availableOptions=q_data.get("availableOptions"),
                correctAnswers=q_data.get("correctAnswers"),
                totalMarks=q_data["totalMarks"],
                explanation=explanation,
                skillType=SkillType(q_data["skillType"]),
                referenceParagraphs=q_data.get("referenceParagraphs", [])
            )
            questions.append(question)
        
        return {
            "passage": passage,
            "questions": questions,
            "answers": answers_data
        }
        
    except FileNotFoundError as e:
        logger.error(f"数据文件未找到: {e}")
        raise HTTPException(
            status_code=500,
            detail="题目数据文件未找到，请联系管理员"
        )
    except json.JSONDecodeError as e:
        logger.error(f"JSON解析错误: {e}")
        raise HTTPException(
            status_code=500,
            detail="题目数据格式错误，请联系管理员"
        )
    except Exception as e:
        logger.error(f"加载Demo数据失败: {e}")
        raise HTTPException(
            status_code=500,
            detail="加载题目数据时发生未知错误"
        )


@router.get(
    "/demo-questions",
    response_model=DemoQuestionsResponse,
    summary="获取Demo题目数据",
    description="获取DSE英文阅读理解Demo的文章内容和题目数据",
    response_description="包含文章和题目的完整数据"
)
async def get_demo_questions() -> DemoQuestionsResponse:
    """
    获取Demo题目数据
    
    返回DSE阅读理解Demo的完整题目数据，包括：
    - 阅读文章（Flash Fiction主题）
    - 3道真题（词汇题、细节题、时序题）
    - 题目元数据（总分、建议用时等）
    
    Returns:
        DemoQuestionsResponse: Demo题目数据响应
        
    Raises:
        HTTPException: 数据加载失败时返回500错误
    """
    logger.info("收到获取Demo题目数据请求")
    
    try:
        data = await load_demo_data()
        
        # 计算总分
        total_marks = sum(q.totalMarks for q in data["questions"])
        
        response = DemoQuestionsResponse(
            passage=data["passage"],
            questions=data["questions"],
            total_marks=total_marks,
            estimated_time=30  # 建议30分钟完成
        )
        
        logger.info(f"成功返回Demo题目数据，包含{len(data['questions'])}道题目")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取Demo题目数据失败: {e}")
        raise HTTPException(
            status_code=500,
            detail="获取题目数据时发生未知错误"
        )


@router.post(
    "/submit",
    response_model=SubmissionResponse,
    summary="提交答案进行批改",
    description="提交用户答案，启动AI老师批改流程",
    response_description="返回提交ID和批改状态"
)
async def submit_answers(
    request: SubmitAnswersRequest,
    background_tasks: BackgroundTasks
) -> SubmissionResponse:
    """
    提交答案进行批改
    
    接收用户提交的答案，生成唯一的提交ID，并在后台启动AI老师批改流程。
    批改过程是异步的，客户端需要通过提交ID轮询获取批改结果。
    
    Args:
        request: 提交答案请求，包含用户答案和答题时间
        background_tasks: FastAPI后台任务管理器
        
    Returns:
        SubmissionResponse: 包含提交ID和状态信息
        
    Raises:
        HTTPException: 请求验证失败时返回400错误
    """
    logger.info(f"收到答案提交请求，包含{len(request.answers)}个答案")
    
    try:
        # 生成提交ID
        submission_id = f"submission_{int(datetime.now().timestamp())}"
        
        # 初始化提交记录
        submission_store[submission_id] = {
            "status": "processing",
            "progress": 0,
            "message": "AI老师正在批改中...",
            "request": request.dict(),
            "created_at": datetime.now(),
            "result": None,
            "error_detail": None
        }
        
        # 启动后台批改任务
        background_tasks.add_task(
            process_grading,
            submission_id,
            request
        )
        
        logger.info(f"答案提交成功，提交ID: {submission_id}")
        
        return SubmissionResponse(
            submission_id=submission_id,
            status="processing",
            message="答案已提交，AI老师正在批改中...",
            estimated_completion_time=60  # 预计60秒完成
        )
        
    except Exception as e:
        logger.error(f"提交答案失败: {e}")
        raise HTTPException(
            status_code=500,
            detail="提交答案时发生错误，请重试"
        )


@router.get(
    "/results/{submission_id}",
    response_model=GradingStatusResponse,
    summary="查询批改结果",
    description="根据提交ID查询批改进度和结果",
    response_description="批改状态和结果数据"
)
async def get_grading_results(submission_id: str) -> GradingStatusResponse:
    """
    查询批改结果
    
    根据提交ID查询AI老师批改的进度和结果。支持三种状态：
    - processing: 批改进行中
    - completed: 批改完成，返回详细结果
    - failed: 批改失败，返回错误信息
    
    Args:
        submission_id: 答案提交时返回的唯一ID
        
    Returns:
        GradingStatusResponse: 批改状态和结果
        
    Raises:
        HTTPException: 提交ID不存在时返回404错误
    """
    logger.info(f"查询批改结果，提交ID: {submission_id}")
    
    if submission_id not in submission_store:
        logger.warning(f"提交ID不存在: {submission_id}")
        raise HTTPException(
            status_code=404,
            detail="提交记录不存在，请检查提交ID是否正确"
        )
    
    submission = submission_store[submission_id]
    
    response = GradingStatusResponse(
        submission_id=submission_id,
        status=submission["status"],
        progress=submission["progress"],
        message=submission["message"],
        result=submission.get("result"),
        error_detail=submission.get("error_detail")
    )
    
    logger.info(f"返回批改状态: {submission['status']}")
    return response


async def process_grading(submission_id: str, request: SubmitAnswersRequest):
    """
    后台批改处理函数
    
    这是在后台执行的批改流程，包括：
    1. 更新批改进度
    2. 调用AI Teacher服务
    3. 处理批改结果
    4. 更新最终状态
    
    Args:
        submission_id: 提交ID
        request: 用户提交的答案请求
    """
    logger.info(f"开始处理批改任务: {submission_id}")
    
    try:
        # 更新进度: 开始批改
        submission_store[submission_id].update({
            "progress": 10,
            "message": "正在分析用户答案..."
        })
        
        # 加载Demo数据
        data = await load_demo_data()
        
        # 更新进度: 数据准备完成
        submission_store[submission_id].update({
            "progress": 30,
            "message": "正在调用AI老师..."
        })
        
        # 创建AI Teacher服务实例
        ai_teacher = AITeacherService()
        
        # 执行批改
        result = await ai_teacher.grade_answers(
            passage=data["passage"],
            questions=data["questions"],
            user_answers=request.answers,
            time_spent=(request.end_time - request.start_time).total_seconds()
        )
        
        # 更新进度: 批改完成
        submission_store[submission_id].update({
            "status": "completed",
            "progress": 100,
            "message": "批改完成",
            "result": result
        })
        
        logger.info(f"批改任务完成: {submission_id}")
        
    except Exception as e:
        logger.error(f"批改任务失败: {submission_id}, 错误: {e}")
        
        # 更新错误状态
        submission_store[submission_id].update({
            "status": "failed",
            "progress": 0,
            "message": "批改失败",
            "error_detail": str(e)
        })


# ===== 健康检查和其他工具接口 =====

@router.get(
    "/health",
    summary="健康检查",
    description="检查DSE服务状态",
    tags=["System"]
)
async def health_check():
    """DSE服务健康检查"""
    return {
        "status": "healthy",
        "service": "DSE API",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }


@router.get(
    "/submissions",
    summary="获取提交记录列表",
    description="获取所有提交记录（调试用）",
    tags=["Debug"]
)
async def get_submissions():
    """获取所有提交记录（仅用于调试）"""
    return {
        "total": len(submission_store),
        "submissions": {
            sid: {
                "status": data["status"],
                "progress": data["progress"],
                "created_at": data["created_at"].isoformat()
            }
            for sid, data in submission_store.items()
        }
    }