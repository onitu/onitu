logs = {
    'driver_started': (
        ("{driver}", "Started"),
        ("{driver} - Router", "Started"),
        ("{driver} - Dealer", "Started"),
    ),
    'referee_started': (
        ("Referee", "Started"),
    ),
    'transfer_started': (
        (
            "{d_to} - Dealer",
            "Starting to get '{filename}' from {d_from}"
        ),
    ),
    'transfer_ended': (
        (
            "{d_to} - Dealer",
            "Transfer of '{filename}' from {d_from} successful"
        ),
    ),
    'transfer_aborted': (
        (
            "{d_to} - Dealer",
            "Aborting transfer of '{filename}' from {d_from}"
        ),
    ),
    'transfer_restarted': (
        (
            "{d_to} - Dealer",
            "Restarting transfer of '{filename}' from {d_from}"
        ),
    ),
}
