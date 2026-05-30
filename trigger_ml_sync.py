
import asyncio
from app.tasks.sync_ml_insights import sync_ml_insights_async

async def main():
    print("Starting ML sync...")
    result = await sync_ml_insights_async()
    print(f"ML sync result: {result}")

if __name__ == "__main__":
    asyncio.run(main())
