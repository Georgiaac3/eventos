from .eventbrite import Eventbrite
from .ics_source import harvard, sloan
from .luma import Luma
from .partiful import Partiful

CONNECTORS = {c.id: c for c in (Luma(), Eventbrite(), sloan, harvard, Partiful())}

LABEL = {"luma": "Luma", "eventbrite": "Eventbrite", "sloan": "Sloan Groups", "harvard": "Harvard", "partiful": "Partiful"}


def connector_for(ev):
    return CONNECTORS[ev["platform"]]
