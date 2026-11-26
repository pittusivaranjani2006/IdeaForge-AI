import asyncio
from openai import AsyncOpenAI
from dotenv import dotenv_values

config = dotenv_values(".env")

client = AsyncOpenAI(
    api_key=config.get("OPENAI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

async def test_gemini():
    try:
        response = await client.chat.completions.create(
            model="gemini-2.5-flash",
            messages=[
                {
                    "role": "user",
                    "content": "Generate two AI project ideas. Return JSON."
                }
            ],
            response_format={"type": "json_object"},
            max_tokens=1000
        )

        print("SUCCESS!")
        print(response.choices[0].message.content)

    except Exception as e:
        print("ERROR:")
        print(repr(e))

    finally:
        await client.close()

asyncio.run(test_gemini())