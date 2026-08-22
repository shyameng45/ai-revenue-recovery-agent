"""
AI Service
----------
Talks to OpenAI to do two things per failed payment:
  1. Diagnosis: a short, human-readable note on why it likely failed and
     what the recommended recovery action is.
  2. Recovery message: a warm, non-pushy Hinglish reminder to send the
     customer (or a "please update your card" nudge for hard fails).
"""
import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)
MODEL = "openai/gpt-oss-20b"


def diagnose_and_generate_message(customer_name: str, plan_name: str, amount: float,
                                    failure_reason: str, classification: str) -> dict:
    """
    Calls OpenAI once to get both a diagnosis note and a Hinglish recovery
    message, returned as a dict: {"diagnosis": str, "message": str}.
    """
    system_prompt = (
        "You are a payments recovery assistant for an Indian fintech company. "
        "Given a failed subscription payment, you must:\n"
        "1. Write a one-sentence diagnosis of why it likely failed and what "
        "the recommended action is (retry / ask for new card / wait).\n"
        "2. Write a short, warm, non-pushy reminder message in natural Hinglish "
        "(Hindi-English mix, casual and respectful, like how young urban Indians "
        "text) to send the customer. Do not sound like a robotic collections agency. "
        "Keep it under 3 sentences.\n\n"
        "Respond ONLY in valid JSON with keys: diagnosis, message."
    )

    user_prompt = (
        f"Customer: {customer_name}\n"
        f"Plan: {plan_name}\n"
        f"Amount: Rs.{amount}\n"
        f"Failure reason: {failure_reason}\n"
        f"Classification: {classification} fail\n"
    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.7,
    )

    content = response.choices[0].message.content
    try:
        parsed = json.loads(content)
        return {
            "diagnosis": parsed.get("diagnosis", ""),
            "message": parsed.get("message", ""),
        }
    except json.JSONDecodeError:
        return {"diagnosis": "AI response parsing failed.", "message": ""}
