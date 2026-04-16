"""Example 01 — Hello, μOS.

Shows:
 - @tool decorator
 - Agent convenience wrapper
 - ISA trace printout

Runs against MockDriver (no API key needed). Swap in AnthropicDriver or
OpenAIDriver to run against a real model.
"""
from uos import Agent, tool
from uos.drivers.mock import MockDriver


@tool
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


if __name__ == "__main__":
    driver = MockDriver(script=[
        'CALL add {"a": 17, "b": 25}',
        'CALL add {"a": 42, "b": 42}',
        'DONE 84',
    ])

    agent = Agent(
        goal="Compute 17 + 25, then double the result.",
        tools=[add],
        driver=driver,
        budget_tokens=4000,
    )
    result = agent.run()

    print(f"answer: {result.answer}")
    print(f"tokens consumed: {result.tokens_consumed}")
    print("\ntrace:")
    print(result.trace.summary())
