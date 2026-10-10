import time

def tick(last_interaction_timestamp: float | None, current_hour: int, active_facts: bool, caregiver_updates: bool) -> str | None:
    """
    Evaluates whether a proactive event should fire based on time and state.
    Returns the trigger_type if it should fire, otherwise None.
    """
    if last_interaction_timestamp is None:
        return None

    hours_since_active = (time.time() - last_interaction_timestamp) / 3600.0
    if hours_since_active < 4:
        return None  # Too soon since last interaction

    # 1. Morning Greeting: 8 AM - 10 AM
    if 8 <= current_hour <= 10:
        return 'morning'

    # 2. Reminders: Priority over hobbies, throughout the day
    if caregiver_updates and 10 < current_hour < 19:
        return 'reminder'

    # 3. Hobby Check-in: Afternoon
    if active_facts and 12 <= current_hour <= 16:
        return 'hobby'

    # 4. Generic Check-in: Evening
    if 17 <= current_hour <= 20:
        return 'silence'

    return None
