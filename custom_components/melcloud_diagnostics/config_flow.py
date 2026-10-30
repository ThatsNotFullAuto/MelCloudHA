"""Setup and explicit double-confirmation UI; no command services or writable entities."""

import hashlib

import voluptuous as vol
from aiomelcloudhome import MelCloudHomeAuth
from aiomelcloudhome.exceptions import MelCloudHomeAuthenticationError, MelCloudHomeError
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import ALLOW_CONTROL, DOMAIN
from .core.cloud import AuthenticationError, CloudError, CloudReader
from .core.control import FIELDS, ControlError, field_details
from .core.models import DataError
from .discovery import account_label, async_local_hints, existing_accounts
from .presentation import field_label, outcome_message


async def validate_credentials(hass, data):
    from datetime import UTC, datetime

    session = async_get_clientsession(hass)
    auth = MelCloudHomeAuth(data["email"], data["password"], session=session)
    return await CloudReader(session, auth).discover(datetime.now(UTC))


class DiagnosticConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self):
        super().__init__()
        self._accounts = {}
        self._units = {}
        self._credentials = None
        self._selected_ids = []
        self._local_summary = ""

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return await self.async_step_search()
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

    async def async_step_search(self, user_input=None):
        self._accounts = existing_accounts(self.hass)
        hints, status = await async_local_hints(self.hass)
        # Display untrusted discovery labels as plain text without Markdown formatting.
        names = []
        for hint in hints:
            name = " ".join(hint.name.split())[:80].translate(str.maketrans("", "", "[]<>*_`"))
            origin = (
                "già registrato in HA"
                if hint.source == "home_assistant"
                else "rilevato in rete, da verificare"
            )
            names.append(f"{name} ({origin})")
        self._local_summary = (
            ", ".join(names)
            if names
            else (
                "Ricerca locale non disponibile"
                if status == "unavailable"
                else "Nessun candidato locale riconosciuto"
            )
        )
        return await self.async_step_discovery()

    async def async_step_discovery(self, user_input=None):
        errors = {}
        if user_input is not None:
            choice = user_input.get("account")
            if choice == "manual":
                return await self.async_step_account()
            if choice in self._accounts:
                entry = self._accounts[choice]
                return await self.async_step_account(
                    {"email": entry.data["email"], "password": entry.data["password"]}
                )
            errors["base"] = "account_missing"
        options = [
            {"value": k, "label": f"MELCloud Home: {account_label(e.data['email'])}"}
            for k, e in self._accounts.items()
        ]
        options.append({"value": "manual", "label": "Accedi con un altro account / Sign in"})
        return self.async_show_form(
            step_id="discovery",
            errors=errors,
            description_placeholders={
                "local_devices": self._local_summary,
                "accounts": str(len(self._accounts)),
            },
            data_schema=vol.Schema(
                {vol.Required("account"): SelectSelector(SelectSelectorConfig(options=options))}
            ),
        )

    async def async_step_account(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                units = await validate_credentials(self.hass, user_input)
            except (AuthenticationError, MelCloudHomeAuthenticationError):
                errors["base"] = "invalid_auth"
            except (CloudError, MelCloudHomeError, DataError):
                errors["base"] = "cannot_connect"
            else:
                if not units:
                    errors["base"] = "no_units"
                else:
                    await self.async_set_unique_id(
                        hashlib.sha256(user_input["email"].strip().lower().encode()).hexdigest()
                    )
                    self._abort_if_unique_id_configured()
                    self._credentials = {
                        "email": user_input["email"],
                        "password": user_input["password"],
                    }
                    self._units = units
                    return await self.async_step_units()
        return self.async_show_form(
            step_id="account",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required("email"): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.EMAIL)
                    ),
                    vol.Required("password"): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
        )

    async def async_step_units(self, user_input=None):
        errors = {}
        if not self._units or self._credentials is None:
            return self.async_abort(reason="restart_setup")
        if user_input is not None:
            selected = user_input.get("unit_ids", [])
            if (
                isinstance(selected, list)
                and selected
                and all(identifier in self._units for identifier in selected)
            ):
                self._selected_ids = list(dict.fromkeys(selected))
                return await self.async_step_finish()
            errors["base"] = "select_unit"
        options = [{"value": k, "label": s.name} for k, s in self._units.items()]
        return self.async_show_form(
            step_id="units",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required("unit_ids", default=list(self._units)): SelectSelector(
                        SelectSelectorConfig(options=options, multiple=True)
                    )
                }
            ),
        )

    async def async_step_finish(self, user_input=None):
        if not self._selected_ids or self._credentials is None:
            return self.async_abort(reason="restart_setup")
        if user_input is not None:
            return self.async_create_entry(
                title="MELCloud Diagnostics",
                data={**self._credentials, "unit_ids": self._selected_ids},
                options={ALLOW_CONTROL: False},
            )
        return self.async_show_form(
            step_id="finish",
            data_schema=vol.Schema({}),
            description_placeholders={
                "units": ", ".join(self._units[k].name for k in self._selected_ids)
            },
        )

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        errors = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            data = {**entry.data, "password": user_input["password"]}
            try:
                await validate_credentials(self.hass, data)
            except (AuthenticationError, MelCloudHomeAuthenticationError):
                errors["base"] = "invalid_auth"
            except (CloudError, MelCloudHomeError, DataError):
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(entry, data_updates=data)
        return self.async_show_form(
            step_id="reauth_confirm",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required("password"): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    )
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return DiagnosticOptionsFlow()


class DiagnosticOptionsFlow(config_entries.OptionsFlow):
    _proposal = None
    _outcome = None
    _selection = None

    def _language(self):
        return self.hass.config.language or "en"

    def _runtime(self):
        runtime = getattr(self.config_entry, "runtime_data", None)
        if runtime is None or runtime.gate is None:
            raise ControlError("Integrazione non caricata")
        return runtime

    def _cancel(self):
        if self._proposal is not None:
            runtime = getattr(self.config_entry, "runtime_data", None)
            if runtime:
                runtime.gate.pending.pop(self._proposal.token, None)
            self._proposal = None

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(
            step_id="init", menu_options=["dashboard", "settings", "change"]
        )

    async def async_step_dashboard(self, user_input=None):
        from homeassistant.util.yaml import dump

        from .dashboard import dashboard_for_entry

        if user_input is not None:
            return self.async_create_entry(title="", data=dict(self.config_entry.options))
        try:
            self._runtime()
        except ControlError:
            return self.async_abort(reason="not_loaded")
        config = dashboard_for_entry(self.hass, self.config_entry)
        if config is None:
            return self.async_abort(reason="entities_not_ready")
        return self.async_show_form(
            step_id="dashboard",
            data_schema=vol.Schema({}),
            description_placeholders={"yaml": dump(config)},
        )

    async def async_step_settings(self, user_input=None):
        if user_input is not None:
            self._cancel()
            # Revocation is immediate, not deferred until options reload completes.
            runtime = getattr(self.config_entry, "runtime_data", None)
            if runtime and not user_input[ALLOW_CONTROL]:
                runtime.gate.invalidate()
            return self.async_create_entry(
                title="",
                data={**self.config_entry.options, ALLOW_CONTROL: user_input[ALLOW_CONTROL]},
            )
        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        ALLOW_CONTROL, default=self.config_entry.options.get(ALLOW_CONTROL, False)
                    ): bool,
                }
            ),
        )

    async def async_step_change(self, user_input=None):
        try:
            runtime = self._runtime()
            if not self.config_entry.options.get(ALLOW_CONTROL, False):
                return self.async_abort(reason="control_disabled")
        except ControlError:
            return self.async_abort(reason="not_loaded")
        errors = {}
        if user_input is not None:
            self._cancel()
            if (
                user_input.get("unit_id") not in runtime.data
                or user_input.get("field") not in FIELDS
            ):
                errors["base"] = "select_parameter"
            else:
                self._selection = (user_input["unit_id"], user_input["field"])
                return await self.async_step_value()
        return self.async_show_form(
            step_id="change",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required("unit_id"): vol.In({k: s.name for k, s in runtime.data.items()}),
                    vol.Required("field"): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                {"value": k, "label": field_label(k, self._language())}
                                for k in FIELDS
                            ]
                        )
                    ),
                }
            ),
        )

    async def async_step_value(self, user_input=None):
        from datetime import UTC, datetime

        if self._selection is None:
            return self.async_abort(reason="proposal_invalid")
        identifier, field = self._selection
        errors = {}
        detail = ""
        try:
            runtime = self._runtime()
            snapshot = await runtime.reader.read_unit(identifier, datetime.now(UTC))
            details = field_details(snapshot, field)
        except (ControlError, CloudError, MelCloudHomeError, DataError):
            return self.async_abort(reason="parameter_unavailable")
        if user_input is not None:
            try:
                self._proposal = await runtime.gate.propose(
                    self.flow_id, identifier, field, user_input["value"]
                )
            except (ControlError, CloudError, MelCloudHomeError, DataError) as err:
                errors["base"] = "proposal_failed"
                detail = (
                    str(err)
                    if isinstance(err, ControlError)
                    else "Lettura cloud non riuscita: riprova più tardi"
                )
            else:
                return await self.async_step_confirm_first()
        return self.async_show_form(
            step_id="value",
            errors=errors,
            description_placeholders={
                "unit": snapshot.name,
                "field": field_label(field, self._language()),
                "old": str(details["old"]),
                "minimum": str(details["minimum"]),
                "maximum": str(details["maximum"]),
                "detail": detail,
            },
            data_schema=vol.Schema(
                {
                    vol.Required("value"): NumberSelector(
                        NumberSelectorConfig(
                            min=details["minimum"],
                            max=details["maximum"],
                            step=details["increment"],
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="°C",
                        )
                    )
                }
            ),
        )

    def _preview(self):
        p = self._proposal
        return {
            "unit": self._runtime().data[p.unit].name
            if p.unit in self._runtime().data
            else "Pompa di calore",
            "field": field_label(p.field, self._language()),
            "old": str(p.context["old"]),
            "new": str(p.value),
            "minimum": str(p.context["minimum"]),
            "maximum": str(p.context["maximum"]),
        }

    async def async_step_confirm_first(self, user_input=None):
        if self._proposal is None:
            return self.async_abort(reason="proposal_invalid")
        if user_input is not None:
            if user_input.get("confirm") is not True:
                self._cancel()
                return self.async_abort(reason="cancelled")
            try:
                self._proposal = await self._runtime().gate.confirm_first(
                    self._proposal.token, self.flow_id
                )
            except (ControlError, CloudError, MelCloudHomeError, DataError):
                self._cancel()
                return self.async_abort(reason="proposal_invalid")
            return await self.async_step_confirm_final()
        return self.async_show_form(
            step_id="confirm_first",
            description_placeholders=self._preview(),
            data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
        )

    async def async_step_confirm_final(self, user_input=None):
        if self._proposal is None or self._proposal.stage != 1:
            return self.async_abort(reason="proposal_invalid")
        if user_input is not None:
            if user_input.get("confirm") is not True:
                self._cancel()
                return self.async_abort(reason="cancelled")
            try:
                self._outcome = await self._runtime().gate.execute(
                    self._proposal.token, self.flow_id
                )
            except ControlError:
                self._cancel()
                return self.async_abort(reason="proposal_invalid")
            except (CloudError, MelCloudHomeError, DataError, OSError):
                self._cancel()
                return self.async_abort(reason="outcome_unknown")
            self._proposal = None
            await self._runtime().async_request_refresh()
            return await self.async_step_result()
        return self.async_show_form(
            step_id="confirm_final",
            description_placeholders=self._preview(),
            data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
        )

    async def async_step_result(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=dict(self.config_entry.options))
        return self.async_show_form(
            step_id="result",
            data_schema=vol.Schema({}),
            description_placeholders={"outcome": outcome_message(self._outcome, self._language())},
        )
