import asyncio
import json
import redis.asyncio as aioredis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from shared.config import settings

app = FastAPI(
    title="Nex Architectural WebSocket Progress Service",
    description="Asynchronous progress streaming via Redis Pub/Sub."
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Async Redis connection
redis_pool = aioredis.ConnectionPool.from_url(settings.REDIS_URL, decode_responses=True)

@app.get("/health")
async def health_check():
    """Verify service and Redis cache connection states."""
    try:
        client = aioredis.Redis(connection_pool=redis_pool)
        pong = await client.ping()
        return {"status": "healthy", "redis": "connected" if pong else "disconnected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@app.websocket("/ws/progress/{job_id}")
async def websocket_progress_endpoint(websocket: WebSocket, job_id: str):
    """Establishes client socket connection, subscribes to Redis Pub/Sub, and streams updates."""
    await websocket.accept()
    print(f"WebSocket connection established for job: {job_id}")

    # Establish Redis subscriber
    redis_client = aioredis.Redis(connection_pool=redis_pool)
    pubsub = redis_client.pubsub()
    channel_name = f"job_progress_{job_id}"
    
    try:
        # Subscribe to target job channel
        await pubsub.subscribe(channel_name)
        print(f"Subscribed to Redis channel: {channel_name}")

        # Send initial registration acknowledgement
        await websocket.send_json({
            "job_id": job_id,
            "status": "REGISTERED",
            "progress_percent": 0,
            "current_stage": "Queue Connection Established"
        })

        # Infinite loop waiting for Redis events or socket disconnection
        while True:
            # Check for Redis messages with a brief timeout to keep loop alive and responsive
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            
            if message and message.get("type") == "message":
                data_str = message.get("data")
                if data_str:
                    payload = json.loads(data_str)
                    print(f"Streaming Redis payload to WS client: {payload}")
                    await websocket.send_json(payload)
                    
                    # If job completes or fails, we can close the connection cleanly
                    if payload.get("status") in ["COMPLETED", "FAILED"]:
                        await asyncio.sleep(1.0)  # Let the packet deliver fully
                        break
                        
            # Keep-alive ping to check if client socket is still active
            try:
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
                
    except WebSocketDisconnect:
        print(f"WebSocket client disconnected for job: {job_id}")
    except Exception as e:
        print(f"Error in WebSocket progress stream: {e}")
        try:
            await websocket.send_json({"error": "Internal subscription error", "details": str(e)})
        except Exception:
            pass
    finally:
        # Clean up subscriptions and channels
        try:
            await pubsub.unsubscribe(channel_name)
            await pubsub.close()
        except Exception:
            pass
        print(f"Cleaned up Redis subscriptions for job: {job_id}")
