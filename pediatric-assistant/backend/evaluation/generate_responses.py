"""
Generate system responses for all test cases

This script runs all test cases through the system and saves responses
for evaluation by LLM-as-a-Judge.
"""
import json
import asyncio
import sys
from pathlib import Path
from datetime import datetime
from loguru import logger

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.llm_service import llm_service
from app.services.triage_engine import triage_engine
from app.services.rag_service import rag_service
from app.services.safety_filter import safety_filter


async def generate_response(test_case: dict) -> dict:
    """
    Generate system response for a test case

    Args:
        test_case: Test case with id, category, input, expected

    Returns:
        Dict with test case info and system response
    """
    user_input = test_case["input"]
    test_id = test_case["id"]

    logger.info(f"Processing {test_id}: {user_input}")

    try:
        # Step 1: Safety filter (user input)
        safety_result = await safety_filter.check_safety(user_input)

        if safety_result["action"] == "block":
            return {
                "test_id": test_id,
                "category": test_case["category"],
                "input": user_input,
                "expected": test_case["expected"],
                "response": safety_result["message"],
                "metadata": {
                    "action": "blocked",
                    "reason": safety_result["reason"],
                    "triage_level": None,
                    "has_source": False,
                }
            }

        # Step 2: Intent + entities
        intent_result = await llm_service.extract_intent_and_entities(user_input)

        # Step 3: Triage flow
        if intent_result.intent.type == "triage":
            danger_alert = triage_engine.check_danger_signals(intent_result.entities)
            if danger_alert:
                response = danger_alert
                return {
                    "test_id": test_id,
                    "category": test_case["category"],
                    "input": user_input,
                    "expected": test_case["expected"],
                    "response": response,
                    "metadata": {
                        "action": "emergency",
                        "triage_level": "emergency",
                        "danger_signals": intent_result.entities.get("danger_signals", []),
                        "has_source": False,
                    }
                }

            symptom = intent_result.entities.get("symptom", "")
            missing_slots = triage_engine.get_missing_slots(symptom, intent_result.entities)
            if missing_slots:
                follow_up = triage_engine.generate_follow_up_question(symptom, missing_slots)
                return {
                    "test_id": test_id,
                    "category": test_case["category"],
                    "input": user_input,
                    "expected": test_case["expected"],
                    "response": follow_up,
                    "metadata": {
                        "action": "follow_up",
                        "triage_level": None,
                        "follow_up_questions": missing_slots,
                        "has_source": False,
                    }
                }

            decision = triage_engine.make_triage_decision(symptom, intent_result.entities)
            response = f"**{decision.reason}**\n\n{decision.action}"
            response = safety_filter.add_disclaimer(response)
            return {
                "test_id": test_id,
                "category": test_case["category"],
                "input": user_input,
                "expected": test_case["expected"],
                "response": response,
                "metadata": {
                    "action": "triage",
                    "triage_level": decision.level,
                    "has_source": False,
                }
            }

        # Step 4: RAG consult
        rag_result = await rag_service.generate_answer_with_sources(user_input)
        safety_out = safety_filter.filter_output(rag_result.answer)
        if not safety_out.is_safe:
            return {
                "test_id": test_id,
                "category": test_case["category"],
                "input": user_input,
                "expected": test_case["expected"],
                "response": safety_out.fallback_message,
                "metadata": {
                    "action": "blocked",
                    "reason": "safety_filter",
                    "triage_level": None,
                    "has_source": False,
                }
            }

        response = rag_result.answer
        response = safety_filter.add_disclaimer(response)
        return {
            "test_id": test_id,
            "category": test_case["category"],
            "input": user_input,
            "expected": test_case["expected"],
            "response": response,
            "metadata": {
                "action": "consult",
                "triage_level": None,
                "has_source": rag_result.has_source,
                "source_count": len(rag_result.sources),
                "model_used": None,
            }
        }

    except Exception as e:
        logger.error(f"Error processing {test_id}: {e}", exc_info=True)
        return {
            "test_id": test_id,
            "category": test_case["category"],
            "input": user_input,
            "expected": test_case["expected"],
            "response": f"系统错误: {str(e)}",
            "metadata": {
                "action": "error",
                "error": str(e),
            }
        }


async def main():
    """Main function to generate all responses"""

    # Load test cases
    test_cases_path = Path(__file__).parent.parent / "app" / "data" / "test_cases.json"

    with open(test_cases_path, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    logger.info(f"Loaded {len(test_cases)} test cases")

    # Generate responses
    results = []

    # Process with concurrency limit
    semaphore = asyncio.Semaphore(3)  # Limit to 3 concurrent requests

    async def process_with_limit(test_case):
        async with semaphore:
            return await generate_response(test_case)

    tasks = [process_with_limit(tc) for tc in test_cases]
    results = await asyncio.gather(*tasks)

    # Save results
    output_path = Path(__file__).parent / "test_responses.json"

    output_data = {
        "generated_at": datetime.now().isoformat(),
        "total_cases": len(test_cases),
        "results": results
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved {len(results)} responses to {output_path}")

    # Print summary
    print("\n" + "="*60)
    print("Response Generation Summary")
    print("="*60)
    print(f"Total test cases: {len(test_cases)}")
    print(f"Successfully generated: {len(results)}")

    # Count by action
    action_counts = {}
    for result in results:
        action = result["metadata"].get("action", "unknown")
        action_counts[action] = action_counts.get(action, 0) + 1

    print("\nResponses by action:")
    for action, count in sorted(action_counts.items()):
        print(f"  {action}: {count}")

    print(f"\nResults saved to: {output_path}")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
