# Barebones implementation plan

## Keep
- Existing coding-agent runtime and safe execution infrastructure.
- Cloud model/provider plumbing needed by the coding agent.
- Existing persistence/recovery mechanisms where compatible.
- Windows packaging/startup support.
- Voice input/output only where already implemented reliably.

## Replace default UI with
- One conversation/composer surface for text or voice requests.
- One live agent activity/status surface.
- One compact task/recovery status strip.

## Remove from default surface
- Persona selector/custom persona presentation.
- Holodeck/holographic UI.
- Decorative 3D presentation.
- Unrelated feature panels and integrations.

## Verification gates
- TypeScript build passes.
- Python import/startup checks pass.
- Packaged Windows app launches without a terminal.
- User can submit a coding request.
- Activity updates while agent works.
- Files/commands/tests are reflected in activity.
- Restart restores the task/status state.
- Agent reports failure rather than fabricating completion.
