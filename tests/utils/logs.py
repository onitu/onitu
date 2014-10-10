logs = {
    'setup_not_existing': (
        (
            "Onitu",
            "Can't process setup file '{setup}' : "
            "[Errno 2] No such file or directory: '{setup}'"
        ),
    ),
    'setup_invalid': (
        (
            "Onitu",
            "Error parsing '{setup}' : {error}"
        ),
    ),
    'driver_started': (
        ("{driver}", "Started"),
        ("{driver} - Router", "Started"),
        ("{driver} - Dealer", "Started"),
    ),
    'driver_stopped': (
        ("{driver}", "Exited"),
    ),
    'plug_started': (
        ("{driver}", "Started"),
    ),
    'referee_started': (
        ("Referee", "Started"),
    ),
    'api_started': (
        ("REST API", "Starting on localhost:3862"),
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
