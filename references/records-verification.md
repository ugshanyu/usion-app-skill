# Usions Records: implementation and live verification

Read when creating a game or changing SDK initialization, scoring, persistence, or leaderboard integration. This gate applies to those changes, not every unrelated visual edit.

## Keep the host connection recoverable

- A host initialization timeout is not proof the game is standalone. Use the SDK's documented initialization callback to accept late INIT, or another documented mechanism that preserves late recovery. Guard setup against duplicate listeners/submissions. Distinguish standalone, embedded connecting, connected, and failed states.
- Preserve earned scores while waiting for identity or a save acknowledgment. On connection, transfer pending work to the correct account without silently overwriting it, submit, and refresh visible records even if the result screen is already open. Avoid attributing another account's pending score to the current user.
- Clear pending work only after a successful backend acknowledgment. A resolved promise without a successful response, local storage write, or rendered “saved” label is not sufficient. Keep failures retryable. For best-score queues, use the configured ordering; highest is not correct for time trials, ratings, or all progression metrics.
- Regression coverage should include INIT arriving after the former timeout, finishing before INIT, rejected submission followed by retry, and a web iframe as well as any supported native bridge. Tests provide implementation evidence; they do not establish production behavior.

## Verify the deployed path

1. Inspect the intended public service's identity, iframe URL, leaderboard enabled state, metric, mode, and ordering. Confirm the host loads the deployed revision; stale open frames can still run old code.
2. Open the game in the real Usions host under the intended account. Read its existing record as the baseline. Complete a legitimate run using normal controls, retaining the actual earned result. Never inject a fabricated score, reset another user's record, or create an artificial high score for verification. Use an authorized test account when available; respect the task's authorization for production writes and automatic record notifications.
3. Observe the real submission acknowledgment and subsequent records read. Capture the actual run score and resulting best/rank; do not expose auth tokens or raw sensitive logs. Verify Friends and Global display the right account, metric, and result.
4. Open the platform's Records page for that exact game and reload it. Confirm the persisted best and rank are consistent with the submission. In best-score mode a worse run is accepted without replacing the prior best; label the run result and best separately. An unchanged old best alone cannot prove a new submission happened: acknowledgment is still required.
5. Retain a screenshot of the live Records page and concise evidence of the earned submission, account, deployed revision, and fresh read. Report exactly which host/device was observed. Web verification is not physical-device verification.

If authentication, revoked sessions, host loading, or network failures prevent this path, attempt safe recovery within the authorized scope. Do not repeatedly take over an account session that another active client keeps revoking. State what was actually verified and the remaining blocker. “Deployed; live save verification blocked” is accurate; “fixed and verified” is not. An old record can be reported as an existing persisted record, never as proof the new code saved it.
