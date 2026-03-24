import time
from dataclasses import dataclass


@dataclass
class RateLimit:
    rpm: int
    tpm: int
    current_rpm: int = 0
    current_tpm: int = 0
    last_reset: float = time.time()


class CapacityManager:
    """Manages capacity across Jules (concurrency) and LLM APIs (RPM/TPM)."""

    def __init__(self):
        # Default limits based on your Pro subscriptions
        self.limits = {
            "claude-opus": RateLimit(rpm=50, tpm=200_000),
            "claude-sonnet": RateLimit(rpm=1000, tpm=200_000),
            "gemini-flash": RateLimit(rpm=2000, tpm=1_000_000),
            "jules": 5,  # Concurrent tasks
        }
        self.active_jules_tasks = 0

    def reset_if_needed(self, model: str):
        if time.time() - self.limits[model].last_reset >= 60:
            self.limits[model].current_rpm = 0
            self.limits[model].current_tpm = 0
            self.limits[model].last_reset = time.time()

    def has_capacity(self, model: str, estimated_tokens: int = 0) -> bool:
        if model == "jules":
            return self.active_jules_tasks < self.limits["jules"]

        self.reset_if_needed(model)
        limit = self.limits[model]
        return limit.current_rpm < limit.rpm and (limit.current_tpm + estimated_tokens) < limit.tpm

    def consume(self, model: str, tokens: int = 0):
        if model == "jules":
            self.active_jules_tasks += 1
        else:
            self.limits[model].current_rpm += 1
            self.limits[model].current_tpm += tokens

    def release(self, model: str):
        if model == "jules":
            self.active_jules_tasks = max(0, self.active_jules_tasks - 1)


if __name__ == "__main__":
    # Example usage
    cm = CapacityManager()
    print(f"Initial Jules capacity: {cm.has_capacity('jules')}")
    cm.consume("jules")
    print(f"Jules capacity after 1 task: {cm.has_capacity('jules')}")
