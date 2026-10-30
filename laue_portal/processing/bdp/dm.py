"""Use DM's supported Python API through its installed environment.

A development host can use a configured SSH bridge; the deployed portal can
invoke the same API locally. Passwords remain in DM_LOGIN_FILE and never in arguments.
"""

from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path

from laue_portal.processing.bdp.transport import shell_command

_API_SCRIPT = """
import json, sys
from dm.proc_web_service.api.workflowProcApi import WorkflowProcApi
request = json.load(sys.stdin)
api = WorkflowProcApi()
operation, args = request['operation'], request['args']
if operation == 'submit':
    result = api.startProcessingJob(args['owner'], args['workflow'], args['arguments'])
elif operation == 'get':
    try:
        result = api.getProcessingJobById(args['owner'], args['id'])
    except Exception:
        result = api.getProcessingJobRecord(args['id'])
elif operation == 'find':
    result = api.listProcessingJobRecords(queryDict={'submissionId': args['submission_id']}, limit=10)
elif operation == 'restore_permissions':
    from dm.ds_web_service.api.fileDsApi import FileDsApi
    result = FileDsApi().restorePermissions(
        experimentPath=args['relative_path'], experimentName=args['experiment'])
elif operation in ('daqs', 'daq', 'arrival_files'):
    from dm.daq_web_service.api.experimentDaqApi import ExperimentDaqApi
    daq_api = ExperimentDaqApi()
    if operation == 'daqs':
        result = daq_api.listDaqs('any')
    elif operation == 'daq':
        result = daq_api.getDaqInfo(args['id'])
    else:
        from dm.cat_web_service.api.fileCatApi import FileCatApi
        daq = daq_api.getDaqInfo(args['id'])
        files = FileCatApi().getExperimentFiles(
            args['experiment'], queryDict=args['query'], skip=args['skip'],
            limit=args['limit'], keyList=[
                'experimentFilePath', 'storageFilePath', 'fileSize',
                'fileProcessingTime', 'daqId', 'experimentName',
            ])
        result = {'daq_status': daq.get('status'), 'files': files}
else:
    raise ValueError('Unsupported operation')
def serialize(value):
    # DM returns DmObject instances, including ProcessingJob and job lists.
    # Their string representation is a Python dict repr, not an API record.
    if isinstance(getattr(value, 'data', None), dict):
        return value.data
    return str(value)
print(json.dumps(result, default=serialize))
"""


class DMClient:
    def __init__(self, settings):
        self.settings = settings

    def _call(self, operation, **args):
        command = (
            f"source {shlex.quote(self.settings['setup_file'])} >/dev/null; exec python -c {shlex.quote(_API_SCRIPT)}"
        )
        # The setup file supplies the DM environment. Interactive login profiles
        # can print banners or load incompatible modules into this JSON channel.
        argv = shell_command(command, self.settings.get("ssh_host"), login=False)
        result = subprocess.run(
            argv,
            input=json.dumps({"operation": operation, "args": args}),
            capture_output=True,
            text=True,
            check=True,
            timeout=self.settings.get("timeout_seconds", 30),
        )
        return json.loads(result.stdout)

    def submit(self, plan):
        return self._call(
            "submit",
            owner=self.settings["owner"],
            workflow=self.settings["workflow"],
            arguments={
                "submissionId": plan["submission_id"],
                "experimentName": "LauePortal",
                "source": "laue-portal",
                "analysisMachine": plan["backend"],
                # DM requires an input file specification for every job. Use
                # one frozen shared control file, so it runs the workflow once.
                "filePath": str(Path(plan["run_directory"]) / "request.json"),
            },
        )

    def get(self, external_id):
        return self._call("get", owner=self.settings["owner"], id=external_id)

    def find(self, submission_id):
        return self._call("find", submission_id=submission_id)

    def restore_permissions(self, experiment, relative_path):
        return self._call("restore_permissions", experiment=experiment, relative_path=relative_path)

    def daqs(self):
        return self._call("daqs")

    def daq(self, identifier):
        return self._call("daq", id=identifier)

    def arrival_files(self, binding, query, *, skip=0, limit=250):
        return self._call(
            "arrival_files",
            id=binding["daq_id"],
            experiment=binding["experiment"],
            query=query,
            skip=skip,
            limit=limit,
        )

    def cancel(self, submission_id):
        """Request cancellation on the DM VM without a portal-to-workflow-host SSH key."""
        from uuid import UUID

        return self._call(
            "submit",
            owner=self.settings["owner"],
            workflow=self.settings["cancel_workflow"],
            arguments={
                "cancelSubmissionId": str(UUID(submission_id)),
                "source": "laue-portal",
                "filePath": self.settings["launcher_config"],
            },
        )


def launcher_command(settings, action, submission_id):
    """Only UUIDs and fixed administrator settings enter the remote shell."""
    from uuid import UUID

    if action not in {"cancel"}:
        raise ValueError(action)
    command = [
        settings["launcher_python"],
        "-m",
        "laue_portal.processing.bdp.stage",
        "--config",
        settings["launcher_config"],
        action,
        str(UUID(submission_id)),
    ]
    shell = f"cd {shlex.quote(settings['launcher_code'])} && exec {shlex.join(command)}"
    # The API bridge may be on another host, while cancellation must reach the launcher
    # with Globus access. Avoid the VM account's interactive login profile.
    return shell_command(shell, settings.get("launcher_ssh_host", settings.get("ssh_host")), login=False)
