logs = {
    'driver_started': (
        ("{driver}", "Started"),
        ("{driver} - Router", "Started"),
        ("{driver} - Worker", "Started"),
    ),
    'referee_started': (
        ("Referee", "Started"),
    ),
    'transfer_started': (
        (
            "{d_to} - Worker",
            "Starting to get '{filename}' from {d_from}"
        ),
    ),
    'transfer_ended': (
        (
            "{d_to} - Worker",
            "Transfer of '{filename}' from {d_from} successful"
        ),
    ),
    'transfer_aborted': (
        (
            "{d_to} - Router",
            "Aborting transfer of '{filename}' from {d_from}"
        ),
    )
}
