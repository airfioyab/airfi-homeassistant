"""Config flow for the Airfi integration.

Placeholder so config entries can load; the real discovery/manual flow
replaces this file in a later task.
"""

from homeassistant.config_entries import ConfigFlow

from .const import DOMAIN


class AirfiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Placeholder config flow."""

    VERSION = 1
