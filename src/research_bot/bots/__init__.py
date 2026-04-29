from .general import answer as general_answer
from .fas import answer as fas_answer
from .trihybrid import answer as trihybrid_answer

BOTS = {
    "general": general_answer,
    "fas": fas_answer,
    "trihybrid": trihybrid_answer,
}
