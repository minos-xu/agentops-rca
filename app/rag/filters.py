def match_metadata(
    metadata: dict,
    filters: dict | None
) -> bool:

    if not filters:
        return True

    for key, expected_value in (
        filters.items()
    ):

        actual_value = (
            metadata.get(
                key
            )
        )

        if actual_value != expected_value:
            return False

    return True