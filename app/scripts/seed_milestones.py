# app/scripts/seed_milestones.py
import asyncio
from app.controllers.milestone_controller import seed_milestones

async def main():
    result = await seed_milestones()
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
