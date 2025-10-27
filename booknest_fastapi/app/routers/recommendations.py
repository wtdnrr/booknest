# # app/routers/recommendations.py
# from fastapi import APIRouter, Depends
# from app.dependencies import get_db, get_redis_client
# from pydantic import BaseModel
# from app.internal import recommendations_logic as rec
# from sqlalchemy import text


# router = APIRouter()


# class RecommendRequest(BaseModel):
#     user_id: int

# @router.post("/today")
# def recommend_today_book(request: RecommendRequest, db=Depends(get_db)):
#     """
#     오늘의 책 추천 API
#     """
#     try:
#         # 간단한 쿼리 실행하여 DB 연결 상태 확인
#         result = rec.get_today_recommendations(db, user_id=request.user_id)
#         return {"db_status": "ok", "result": result}
#     except Exception as e:
#         return {"db_status": "error", "detail": str(e)}

# @router.post("/recent_tag")
# def recenct_keyword(request: RecommendRequest, db=Depends(get_db), redis=Depends(get_redis_client)):
#     """
#     최근 많이 본 태그의의 책 추천 API
#     """
#     try:
#         result = rec.get_recent_tag_recommendations(db, redis, user_id=request.user_id)
#         return {"db_status": "ok", "result": result}
#     except Exception as e:
#         return {"db_status": "error", "detail": str(e)}


from fastapi import APIRouter, Depends
from app.dependencies import get_redis_client, get_elasticsearch_client
from pydantic import BaseModel
from app.internal import recommendations_logic as rec


router = APIRouter()


class RecommendRequest(BaseModel):
    user_id: int


@router.post("/today")
def recommend_today_book(request: RecommendRequest, es=Depends(get_elasticsearch_client)):
    try:
        result = rec.get_today_recommendations(es, user_id=request.user_id)
        return {"es_status": "ok", "result": result}
    except Exception as e:
        return {"es_status": "error", "detail": str(e)}


@router.post("/recent_tag")
def recenct_keyword(request: RecommendRequest, redis=Depends(get_redis_client), es=Depends(get_elasticsearch_client)):
    try:
        result = rec.get_recent_tag_recommendations(redis, es, user_id=request.user_id)
        return {"es_status": "ok", "result": result}
    except Exception as e:
        return {"es_status": "error", "detail": str(e)}
