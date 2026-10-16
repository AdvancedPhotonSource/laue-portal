"""Run shell commands through SSH even when the remote login shell is tcsh."""

import base64
import shlex


def shell_command(script, host=None, *, login=True):
    bash_option = "-lc" if login else "-c"
    if not host:
        return ["/bin/bash", bash_option, script]
    encoded = base64.b64encode(script.encode()).decode("ascii")
    # Only an alphanumeric base64 token reaches the login shell. JSON stdin is
    # preserved for the Python API instead of being consumed as a shell script.
    wrapper = f'exec /bin/bash {bash_option} "$(printf %s {encoded} | base64 -d)"'
    return ["ssh", "-T", "-o", "BatchMode=yes", host, "/bin/bash -c " + shlex.quote(wrapper)]
