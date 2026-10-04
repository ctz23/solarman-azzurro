"""Discover connection hints, then validate a full snapshot before saving."""
from __future__ import annotations

import asyncio
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import network
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from .api import ProtocolError, SolarmanClient
from .const import (CONF_FULL_INTERVAL, CONF_INTERVAL, CONF_SERIAL, DEFAULT_FULL_INTERVAL,
                    DEFAULT_INTERVAL, DEFAULT_PORT, DOMAIN, MAX_INTERVAL, MIN_INTERVAL)
from .discovery import DiscoveredLogger, async_discover
from .profile import WINDOWS, decode


def schema(defaults=None):
    """Shared manual form; discovered fields remain editable."""
    defaults = defaults or {}
    return vol.Schema({
        vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, "Azzurro")): vol.All(str, vol.Length(min=1)),
        vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): vol.All(str, vol.Length(min=1)),
        vol.Required(CONF_SERIAL, **({"default": defaults[CONF_SERIAL]} if CONF_SERIAL in defaults else {})): vol.All(vol.Coerce(int), vol.Range(min=1, max=4294967295)),
        vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
        vol.Required(CONF_INTERVAL, default=defaults.get(CONF_INTERVAL, DEFAULT_INTERVAL)): vol.All(vol.Coerce(int), vol.Range(min=MIN_INTERVAL, max=MAX_INTERVAL)),
        vol.Required(CONF_FULL_INTERVAL, default=defaults.get(CONF_FULL_INTERVAL, DEFAULT_FULL_INTERVAL)): vol.All(vol.Coerce(int), vol.Range(min=MIN_INTERVAL, max=MAX_INTERVAL)),
    })


async def validate_connection(data):
    """Validate transport and supported profile without storing any changes."""
    client = SolarmanClient(data[CONF_HOST], data[CONF_SERIAL], data.get(CONF_PORT, DEFAULT_PORT))
    try:
        decode(await client.read(WINDOWS))
    except ProtocolError:
        return "unsupported_profile"
    except (OSError, TimeoutError, asyncio.IncompleteReadError):
        return "cannot_connect"
    finally:
        await client.async_close()
    return None


class AzzurroConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._discovery_attempted = False
        self._loggers: dict[str, DiscoveredLogger] = {}

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            user_input = {**user_input, CONF_HOST: user_input[CONF_HOST].strip(), CONF_NAME: user_input[CONF_NAME].strip()}
            for field in (CONF_HOST, CONF_NAME):
                if not user_input[field]:
                    errors[field] = "required"
            if user_input[CONF_FULL_INTERVAL] < user_input[CONF_INTERVAL]:
                errors[CONF_FULL_INTERVAL] = "full_interval_too_short"
            if errors:
                return self.async_show_form(step_id="user", data_schema=schema(user_input), errors=errors)
            await self.async_set_unique_id(str(user_input[CONF_SERIAL]))
            self._abort_if_unique_id_configured()
            if error := await validate_connection(user_input):
                errors["base"] = error
            else:
                return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)
        elif not self._discovery_attempted:
            self._discovery_attempted = True
            try:
                addresses = [str(address) for address in await network.async_get_ipv4_broadcast_addresses(self.hass)]
                loggers = await async_discover(addresses)
            except OSError:
                loggers = []
            configured = {entry.unique_id for entry in self._async_current_entries()}
            self._loggers = {f"{logger.host}/{logger.serial}": logger for logger in loggers
                             if str(logger.serial) not in configured}
            if len(self._loggers) > 1:
                return await self.async_step_select_logger()
            if self._loggers:
                logger = next(iter(self._loggers.values()))
                return self.async_show_form(step_id="user", data_schema=schema({CONF_HOST: logger.host, CONF_SERIAL: logger.serial}), errors={})
        return self.async_show_form(step_id="user", data_schema=schema(user_input), errors=errors)

    async def async_step_select_logger(self, user_input=None):
        """Let the user choose among multiple loggers or use manual setup."""
        if user_input is not None:
            defaults = {}
            if logger := self._loggers.get(user_input["logger"]):
                defaults = {CONF_HOST: logger.host, CONF_SERIAL: logger.serial}
            return self.async_show_form(step_id="user", data_schema=schema(defaults), errors={})
        choices = {key: f"{logger.host} ({logger.serial})" for key, logger in self._loggers.items()}
        choices["manual"] = "Manual setup"
        return self.async_show_form(step_id="select_logger", data_schema=vol.Schema({vol.Required("logger"): SelectSelector(SelectSelectorConfig(
            options=[{"value": key, "label": label} for key, label in choices.items()],
            translation_key="logger"))}))

    async def async_step_reconfigure(self, user_input=None):
        """Update only host/port after validation, retaining logger identity."""
        entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            user_input = {**user_input, CONF_HOST: user_input[CONF_HOST].strip()}
            if not user_input[CONF_HOST]:
                errors[CONF_HOST] = "required"
            elif error := await validate_connection({**entry.data, **user_input}):
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
        defaults = user_input or entry.data
        return self.async_show_form(step_id="reconfigure", data_schema=vol.Schema({
            vol.Required(CONF_HOST, default=defaults[CONF_HOST]): vol.All(str, vol.Length(min=1)),
            vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
        }), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return AzzurroOptionsFlow()


class AzzurroOptionsFlow(config_entries.OptionsFlowWithReload):
    async def async_step_init(self, user_input=None):
        errors = {}
        interval = max(MIN_INTERVAL, self.config_entry.options.get(CONF_INTERVAL,
                       self.config_entry.data.get(CONF_INTERVAL, DEFAULT_INTERVAL)))
        full_interval = max(interval, self.config_entry.options.get(CONF_FULL_INTERVAL,
                            self.config_entry.data.get(CONF_FULL_INTERVAL, DEFAULT_FULL_INTERVAL)))
        if user_input is not None:
            interval = user_input[CONF_INTERVAL]
            full_interval = user_input[CONF_FULL_INTERVAL]
            if full_interval < interval:
                errors[CONF_FULL_INTERVAL] = "full_interval_too_short"
            else:
                return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(step_id="init", data_schema=vol.Schema({
            vol.Required(CONF_INTERVAL, default=interval): vol.All(vol.Coerce(int), vol.Range(min=MIN_INTERVAL, max=MAX_INTERVAL)),
            vol.Required(CONF_FULL_INTERVAL, default=full_interval): vol.All(vol.Coerce(int), vol.Range(min=MIN_INTERVAL, max=MAX_INTERVAL)),
        }), errors=errors)
