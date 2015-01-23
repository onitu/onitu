"""The Referee listen to all the events sent by the entries and
dispatch the files among the entries according to the rules.

At this point the Referee doesn't do anything interesting as all the
entries are synchronised without any specific rule, but this should
change in a near future.
"""

from .referee import Referee
from .cmd import UP, DEL, MOV

__all__ = ['Referee', 'UP', 'DEL', 'MOV']
