"""Gladier transfer → PBS orchestration → return, following DM's boost-corr flow."""

from __future__ import annotations

import copy
import json
import os
from pathlib import PurePosixPath

from laue_portal.processing.bdp.pbs import build_script, fallback, run_pbs_job


def compact_transfer(spec):
    """Retain every explicit file, factoring repeated directory prefixes out of state."""
    groups, indices, items = [], {}, []
    longest = 1
    for item in spec["transfer_items"]:
        source, destination = PurePosixPath(item["source_path"]), PurePosixPath(item["destination_path"])
        key = str(source.parent).rstrip("/") + "/", str(destination.parent).rstrip("/") + "/"
        if key not in indices:
            indices[key] = len(groups)
            groups.append({"source_prefix": key[0], "destination_prefix": key[1]})
        items.append([indices[key], source.name, destination.name, item.get("recursive", False)])
        longest = max(longest, len(json.dumps(item).encode("utf-8")))
    if not items or longest > 60_000:
        raise ValueError("Input transfer needs nonempty items smaller than 60 KB")
    return {
        "source_endpoint_id": spec["source_endpoint_id"],
        "destination_endpoint_id": spec["destination_endpoint_id"],
        "groups": groups,
        "items": items,
        "batch_size": min(100, 60_000 // longest),
    }


TRANSFER_BATCH_EXPRESSION = (
    "[{'source_path': input['input_transfer']['groups'][item[0]]['source_prefix'] + item[1], "
    "'destination_path': input['input_transfer']['groups'][item[0]]['destination_prefix'] + item[2], "
    "'recursive': item[3]} for item in input['input_transfer']['items']["
    "transfer_cursor['offset']:transfer_cursor['offset'] + input['input_transfer']['batch_size']]]"
)


def client_class(settings):
    # Optional workflow dependencies never enter the portal web process.
    from gladier import GladierBaseClient, GladierBaseTool, generate_flow_definition

    from laue_portal.processing.bdp.auth import SDK4UserLoginManager

    def transfer_tool(name, field):
        return type(
            name,
            (GladierBaseTool,),
            {
                "required_input": [field],
                "flow_definition": {
                    "StartAt": name,
                    "States": {
                        name: {
                            "Type": "Action",
                            "ActionUrl": "https://transfer.actions.globus.org/transfer",
                            "Parameters": {
                                "source_endpoint.$": f"$.input.{field}.source_endpoint_id",
                                "destination_endpoint.$": f"$.input.{field}.destination_endpoint_id",
                                "DATA.$": f"$.input.{field}.transfer_items",
                                "verify_checksum": True,
                            },
                            "ResultPath": f"$.{name}",
                            "WaitTime": 86400,
                            "ExceptionOnActionFailure": True,
                            "End": True,
                        }
                    },
                },
            },
        )

    class BatchedInputTransfer(GladierBaseTool):
        required_input = ["input_transfer"]
        flow_definition = {
            "StartAt": "InitInputTransfer",
            "States": {
                "InitInputTransfer": {
                    "Type": "Pass",
                    "Result": {"offset": 0},
                    "ResultPath": "$.transfer_cursor",
                    "Next": "InputTransfer",
                },
                "InputTransfer": {
                    "Type": "Action",
                    "ActionUrl": "https://transfer.actions.globus.org/transfer",
                    "Parameters": {
                        "source_endpoint.$": "$.input.input_transfer.source_endpoint_id",
                        "destination_endpoint.$": "$.input.input_transfer.destination_endpoint_id",
                        "DATA.=": TRANSFER_BATCH_EXPRESSION,
                        "verify_checksum": True,
                    },
                    "ResultPath": "$.InputTransfer",
                    "WaitTime": 86400,
                    "ExceptionOnActionFailure": True,
                    "Next": "AdvanceInputTransfer",
                },
                "AdvanceInputTransfer": {
                    "Type": "ExpressionEval",
                    "Parameters": {
                        "offset.=": "transfer_cursor['offset'] + input['input_transfer']['batch_size']",
                        "has_more.=": "transfer_cursor['offset'] + input['input_transfer']['batch_size'] < len(input['input_transfer']['items'])",
                    },
                    "ResultPath": "$.transfer_cursor",
                    "Next": "MoreInputTransfers",
                },
                "MoreInputTransfers": {
                    "Type": "Choice",
                    "Choices": [
                        {"Variable": "$.transfer_cursor.has_more", "BooleanEquals": True, "Next": "InputTransfer"}
                    ],
                    "Default": "InputsReady",
                },
                "InputsReady": {"Type": "Pass", "End": True},
            },
        }

    @generate_flow_definition(modifiers={run_pbs_job: {"WaitTime": 172800, "ExceptionOnActionFailure": True}})
    class PBSRun(GladierBaseTool):
        action_url = "https://compute.actions.globus.org/v3"
        required_input = ["compute_endpoint", "job_directory", "script", "fallback_summary", "cancel_file"]
        compute_functions = [run_pbs_job]

    @generate_flow_definition
    class LaueBDPClient(GladierBaseClient):
        gladier_tools = [
            BatchedInputTransfer,
            PBSRun,
            transfer_tool("ResultTransfer", "result_transfer"),
        ]
        secret_config_filename = os.path.join(
            settings["state_directory"], f"gladier-{settings.get('auth_profile', 'personal')}.cfg"
        )

        def _determine_login_manager(self, storage):
            client_id, client_secret = self._get_confidential_client_credentials()
            if client_id and client_secret:
                return super()._determine_login_manager(storage)
            return SDK4UserLoginManager(self.client_id, self.app_name, storage=storage)

        def get_flow_definition(self):
            definition = copy.deepcopy(super().get_flow_definition())
            task = definition["States"]["RunPbsJob"]["Parameters"]["tasks"][0]
            task.pop("kwargs.$", None)
            task["kwargs"] = {
                key + ".$": "$.input." + key for key in ("job_directory", "script", "fallback_summary", "cancel_file")
            }
            return definition

    return LaueBDPClient


def flow_input(plan):
    payload = {
        "input": {
            "input_transfer": compact_transfer(plan["input_transfer"]),
            "result_transfer": plan["result_transfer"],
            "compute_endpoint": plan["target"]["compute_endpoint"],
            "job_directory": str(PurePosixPath(plan["control_directory"]).parent),
            "script": build_script(plan),
            "fallback_summary": fallback(plan),
            "cancel_file": plan["control_directory"] + "/cancel.request",
        }
    }
    # Globus limits run state to 200 KB. Reserve room for an expanded batch and action results.
    if len(json.dumps(payload).encode("utf-8")) > 100_000:
        raise ValueError("Compact transfer input exceeds 100 KB; split the selection into separate portal runs")
    return payload
