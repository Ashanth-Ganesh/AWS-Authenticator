# Agent Toolkit for AWS

Configured for this project using the [official AWS setup instructions](https://raw.githubusercontent.com/aws/agent-toolkit-for-aws/refs/heads/main/setup-instructions/setup.md).

| Setting | Value |
| --- | --- |
| AWS CLI profile | `aws-authenticator` |
| Selected project Region | `us-east-2` |
| Experience | New AWS experience |
| Toolkit/MCP service Region | `us-east-1` |
| Codex MCP name | `aws-mcp` |

The service endpoint Region does not change where the assignment's EC2 resources should be created. Confirm your project Region in **AWS Settings → View all projects → Overview → Additional Info → Region**.

## Installed locally

- AWS CLI v2, using the official signed user-local installer.
- `uv` and `uvx`, using the official Astral installer.
- 24 default AWS skills under `%USERPROFILE%\.agents\skills`.
- An `aws-mcp` entry in `%USERPROFILE%\.codex\config.toml` with `AWS_MCP_PROXY_PROFILES=aws-authenticator`. The generated proxy command and arguments were preserved.
- The new AWS experience rules in the repository's [AGENTS.md](../AGENTS.md).

Verification succeeded: AWS identity lookup, toolkit catalog lookup (114 skills), and MCP initialization/tool discovery (8 tools).

Restart VS Code completely and open a new Codex chat so it picks up the updated PATH, skills, and MCP configuration. Existing chats do not automatically acquire the new tools.

## Renew sign-in

Run this in a new PowerShell terminal:

```powershell
aws login --region us-east-2 --profile aws-authenticator
```

The AWS setup guide states that credentials remain valid for 12 hours and can be renewed for up to 90 days without repeating browser authentication. Complete browser authentication when AWS requests it.

To check access:

```powershell
aws sts get-caller-identity --region us-east-2 --profile aws-authenticator
```

To query the toolkit catalog on Windows with UTF-8 output:

```powershell
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
aws agent-toolkit list-available-skills --region us-east-1 --profile aws-authenticator
```

## Switch projects later

Sign in with a different named profile using `aws login --region YOUR_PROJECT_REGION --profile YOUR_PROFILE`. Add the new profile to the space-separated `AWS_MCP_PROXY_PROFILES` value in the MCP configuration, then restart Codex. Update this repository's Region instructions if its deployment target changes.

AWS credentials and login cache files remain in your Windows user profile. Do not copy them into the repository or submit them with the assignment.
