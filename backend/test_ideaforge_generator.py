import asyncio
from app.services.ai_service import (
    _get_client,
    _idea_generation_prompt,
    IDEA_GENERATION_SYSTEM,
    settings
)

async def main():
    params = {
        "domain": "Artificial Intelligence",
        "difficulty": "Beginner",
        "category": "AI/ML",
        "budget": "Low",
        "team_size": 2,
        "preferred_language": "Python",
        "duration_weeks": 4,
        "purpose": "Mini Project",
        "count": 1
    }

    client = _get_client()

    try:
        print("Model:", settings.ai_model)
        print("Testing actual IdeaForge prompt...")

        response = await client.chat.completions.create(
            model=settings.ai_model,
            messages=[
                {
                    "role": "system",
                    "content": IDEA_GENERATION_SYSTEM
                },
                {
                    "role": "user",
                    "content": _idea_generation_prompt(params)
                }
            ],
            temperature=0.8,
            response_format={"type": "json_object"},
            max_tokens=3000
        )

        print("\nSUCCESS!")
        print(response.choices[0].message.content)

    except Exception as e:
        print("\nERROR TYPE:", type(e).__name__)
        print("ERROR:", str(e))

        if hasattr(e, "response"):
            print("GOOGLE RESPONSE:", e.response.text)

    finally:
        await client.close()

asyncio.run(main())