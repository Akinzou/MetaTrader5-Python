# ADR 0004: No GUI automation for Algo Trading

- Status: accepted (3.0.0)

## Context

On retcode 10027 (AutoTrading disabled by the client), 2.x pressed Ctrl+E
through `pyautogui`.

## Decision

Return `ALGO_TRADING_DISABLED` with an instruction, and never send keystrokes.

We chose an explicit error over the hotkey because Ctrl+E *toggles* the
setting (a second call switches it off again). The keystroke also goes to
whichever window has focus, so on a desktop it typed into the user's editor or
browser.

## Consequences

- `pyautogui` is no longer a dependency, and the library works headless.
- Users have to enable Algo Trading once in the terminal.
