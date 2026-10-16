"""Personal-login compatibility for Gladier 0.11 with Globus SDK 4.

Gladier's default mapper uses the removed ``scope_names`` API and does not
recognize Transfer scopes. Use the SDK's public scope collections instead.
Keep this adapter in source rather than changing installed third-party files.
"""

from urllib.parse import urlsplit
from uuid import UUID

import globus_sdk
from gladier.managers.login_manager import UserAppLoginManager
from globus_sdk.scopes import AuthScopes, ComputeScopes, FlowsScopes, Scope, SpecificFlowScopes, TransferScopes


class SDK4UserLoginManager(UserAppLoginManager):
    def get_resource_server(self, scope):
        base = Scope.parse(str(scope)).scope_string
        for collection in (AuthScopes, FlowsScopes, ComputeScopes, TransferScopes):
            if any(base == known.scope_string for known in collection):
                return collection.resource_server

        # A deployed flow has its own resource server. Preserve dependencies
        # on the original scope when the parent passes it to GlobusApp.
        url = urlsplit(base)
        parts = url.path.split("/")
        if (
            url.scheme == "https"
            and url.netloc == "auth.globus.org"
            and not url.query
            and not url.fragment
            and len(parts) == 4
            and parts[:2] == ["", "scopes"]
        ):
            try:
                flow_id = str(UUID(parts[2]))
            except ValueError:
                pass
            else:
                if base == SpecificFlowScopes(flow_id).user.scope_string:
                    return flow_id

        raise ValueError(f"Unable to find resource server for {scope}")


def authorize(client, settings):
    """Prepare collection consent and register the workflow without running it."""
    manager = client.login_manager
    manager.add_requirements([TransferScopes.all])
    if isinstance(manager, SDK4UserLoginManager):
        # These deployment collections are standard GCS mapped collections.
        # Keep dependencies on GlobusApp, rather than Gladier's flat scope set.
        # Otherwise Gladier compares a scope tree with a base token scope and
        # can repeatedly request login even after consent has been granted.
        collection_ids = [settings["storage"][name]["collection_id"] for name in ("aps", "eagle")]
        with globus_sdk.TransferClient(app=manager.globus_app) as transfer:
            transfer.add_app_data_access_scope(collection_ids)
        # Upgrade existing logins with collection consent. GlobusApp checks the
        # aggregate requirements and reuses cached authorization when complete.
        manager.globus_app.add_scope_requirements(manager.scopes_by_resource_server(manager.required_scopes))
        manager.globus_app.login()
    else:
        client.login()
    function_ids = client.get_compute_function_ids()
    client.sync_flow()
    # A newly registered flow can require a second consent for its own scope.
    client.login()
    return {"flow_id": client.get_flow_id(), "function_ids": function_ids}
