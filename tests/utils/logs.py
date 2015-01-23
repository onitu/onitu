logs = {
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
    'file_updated': (
        (
            "Referee",
            "Update for '{filename}' from {d_from} in folder {folder}"
        ),
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
            "Deletion of '{filename}' from {driver} in folder {folder}"
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
            "Moving of '{src}' to '{dest}' from {driver} in folder {folder}"
        ),
    ),
    'move_completed': (
        (
            "{driver} - Dealer",
            "'{src}' moved to '{dest}'"
        ),
    ),
}


rule_authorities = (
    ('folder', "Folder <{folder}>"),
    ('service', "Service <{service}> in Folder <{folder}>"),
    ('source', "Service <{service} (source)> in Folder <{folder}>")
)

for authority, prefix in rule_authorities:

    prefix = prefix + " ignores event for '{filename}' "

    logs['event_{}_ignored_mode'.format(authority)] = ((
        "Referee",
        prefix + "because mode is '{mode}'"
        ),)

    logs['event_{}_ignored_size'.format(authority)] = ((
        "Referee",
        prefix + "due to its size: {size} bytes"
        ),)

    logs['event_{}_ignored_mimetype'.format(authority)] = ((
        "Referee",
        prefix + "due to its mimetype: {mimetype}"
        ),)

    logs['event_{}_ignored_blacklisted'.format(authority)] = ((
        "Referee",
        prefix + "because it is blacklisted"
        ),)

    logs['event_{}_ignored_not_whitelisted'.format(authority)] = ((
        "Referee",
        prefix + "because it is not whitelisted"
        ),)
