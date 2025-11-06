import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional

from ....core.websocket_manager import websocket_manager

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.websocket("/ws/user/{user_id}")
async def websocket_user_endpoint(
    websocket: WebSocket,
    user_id: str,
    job_id: Optional[int] = Query(None)
):
    await websocket_manager.connect_user(websocket, user_id)

    if job_id:
        await websocket_manager.subscribe_to_job(websocket, job_id, user_id)
        logger.info("WebSocket connected with job subscription",
                   user_id=user_id, job_id=job_id)
    else:
        logger.info("WebSocket connected for user", user_id=user_id)

    try:
        await websocket.send_json({
            "type": "connection_established",
            "user_id": user_id,
            "subscribed_job": job_id,
            "message": "Connected to real-time job updates"
        })

        while True:
            try:
                data = await websocket.receive_json()
                message_type = data.get("type")

                if message_type == "subscribe_job":
                    new_job_id = data.get("job_id")
                    if new_job_id:
                        await websocket_manager.subscribe_to_job(websocket, new_job_id, user_id)
                        await websocket.send_json({
                            "type": "subscription_confirmed",
                            "job_id": new_job_id
                        })
                        logger.info("WebSocket subscribed to additional job",
                                   user_id=user_id, job_id=new_job_id)

                elif message_type == "ping":
                    await websocket.send_json({"type": "pong"})

                else:
                    logger.debug("Unknown WebSocket message type",
                               user_id=user_id, message_type=message_type)

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error("Error handling WebSocket message",
                           user_id=user_id, error=str(e))
                break

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected", user_id=user_id)
    except Exception as e:
        logger.error("WebSocket connection error", user_id=user_id, error=str(e))
    finally:
        await websocket_manager.disconnect_user(websocket)


@router.websocket("/ws/jobs/{job_id}")
async def websocket_job_endpoint(websocket: WebSocket, job_id: int):

    user_id = f"user_{job_id}" 

    await websocket_manager.connect_user(websocket, user_id)
    await websocket_manager.subscribe_to_job(websocket, job_id, user_id)

    logger.info("WebSocket connected to specific job", job_id=job_id)

    try:
        await websocket.send_json({
            "type": "connection_established",
            "job_id": job_id,
            "message": f"Connected to job {job_id} updates"
        })

        while True:
            try:
                data = await websocket.receive_json()

                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error("Error in job WebSocket", job_id=job_id, error=str(e))
                break

    except WebSocketDisconnect:
        logger.info("Job WebSocket disconnected", job_id=job_id)
    except Exception as e:
        logger.error("Job WebSocket error", job_id=job_id, error=str(e))
    finally:
        await websocket_manager.disconnect_user(websocket)


@router.get("/ws/stats")
async def websocket_stats():
    return websocket_manager.get_stats()