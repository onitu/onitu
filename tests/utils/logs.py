logs = {
    'driver_started': (
        ("{driver}", "Started"),
        ("{driver} - Router", "Started"),
        ("{driver} - Dealer", "Started"),
    ),
    'plug_started': (
        ("{driver}", "Started"),
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
            "Transfer of '{filename}' from {d_from} aborted"
        ),
    ),
    'transfer_restarted': (
        (
            "{d_to} - Dealer",
            "Restarting transfer of '{filename}' from {d_from}"
        ),
    ),
    'file_deleted': (
        (
            "Referee",
            "Deletion of '{filename}' from {driver}"
        ),
    ),
    'deletion_completed': (
        (
            "{driver} - Dealer",
            "'{filename}' deleted"
        ),
    ),
    'file_moved': (
        (
            "Referee",
            "Moving of '{src}' to '{dest}' from {driver}"
        ),
    ),
    'move_completed': (
        (
            "{driver} - Dealer",
            "'{src}' moved to '{dest}'"
        ),
    ),
}
