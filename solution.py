
def decide(observation, state):

    if state is None:
        state = {}

    current_slot = int(observation["slot"])
    capacity = int(observation["capacity_units"])
    horizon = int(observation["horizon_slots"])

    jobs = observation.get("jobs", [])
    tariffs = observation.get("tariff_gbp_per_kwh", [])
    forecasts = observation.get("forecast", [])

    unit_kwh = float(observation.get("unit_kwh", 1))
    carbon_price = float(
        observation.get("carbon_price_gbp_per_kg", 0)
    )

    # Get carbon forecast for each future slot.
    carbon_by_slot = {}

    for item in forecasts:
        try:
            s = int(item["slot"])
            c = float(item["carbon_g_per_kwh"])

            if c >= 0:
                carbon_by_slot[s] = c

        except (KeyError, TypeError, ValueError):
            continue

    current_carbon = carbon_by_slot.get(current_slot, 0)

    # Calculate estimated joint cost for each slot.
    slot_cost = {}

    for s in range(current_slot, horizon):

        if s >= len(tariffs):
            break

        tariff = float(tariffs[s])
        carbon = carbon_by_slot.get(s, current_carbon)

        slot_cost[s] = unit_kwh * (
            tariff + carbon_price * carbon / 1000
        )

    # Reserve the available capacity in every future slot.
    free_capacity = {
        s: capacity
        for s in slot_cost
    }

    planned_dispatch = {}

    # Process jobs in earliest-deadline-first order.
    ordered_jobs = sorted(
        jobs,
        key=lambda job: (
            int(job["deadline"]),
            int(job["release"]),
            job["id"]
        )
    )

    for job in ordered_jobs:

        job_id = job["id"]
        remaining = int(job["remaining_units"])
        deadline = int(job["deadline"])

        if remaining <= 0:
            continue

        # A deadline is exclusive.
        possible_slots = [
            s for s in free_capacity
            if current_slot <= s < deadline
            and free_capacity[s] > 0
        ]

        # Prefer the cheapest slots before this job's deadline.
        possible_slots.sort(
            key=lambda s: (slot_cost[s], s)
        )

        for s in possible_slots:

            if remaining <= 0:
                break

            allocation = min(
                remaining,
                free_capacity[s]
            )

            if allocation > 0:

                planned_dispatch.setdefault(s, {})
                planned_dispatch[s][job_id] = allocation

                free_capacity[s] -= allocation
                remaining -= allocation

    # Execute only the current slot's planned allocations.
    dispatch = planned_dispatch.get(current_slot, {})

    return {
        "action": {
            "dispatch": dispatch
        },
        "state": {
            "version": 5,
            "last_slot": current_slot
        }
    }
