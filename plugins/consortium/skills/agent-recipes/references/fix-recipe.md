# Fix recipe

Use the manager's [routing, dispatch and evidence rules](manager.md).
Run searcher before each write brief, fill the [brief template](brief-template.md),
check the brief and size the predicted crew before building.

1. Dispatch **investigator** for a `case.v1` report in an assigned worktree.
   Require reproduction, root cause at file and line, every caller, a test
   that fails for that cause, and fix options. It writes only tests and
   leaves the failure intact. Missing reproduction stops the recipe.
2. **The owner picks the fix** at the owner's gate. Present the case and
   tradeoffs, ask in chat using the host's gate controls, and wait for the
   choice before implementation.
3. Dispatch **implementer** in the investigator's worktree with the chosen
   fix, the failing test and the complete caller and test list. It makes
   the test pass, runs its done-means commands and leaves edits uncommitted.
4. Run **`consortium checks --diff <base>`** in that worktree and run all
   checks it names. Every named gate stops the job; unavailable reviewers
   require manager review rather than being skipped.
5. Run **`consortium gate --worktree <worktree> --wait`**. Read its report,
   test exit code and cleanup results; a failing gate blocks the recipe.
6. Dispatch **device-qa** when a user can see the change, with the assigned
   build, device, platform, persona and flows. Require observed behavior
   and safe screenshots from the running app, scanned before publication.
7. Perform **manager review** of the complete diff, every decision and all
   evidence. Verify the original failure now passes and Scope was kept.
   Resolve findings and rerun checks for any resulting code changes.
8. The **manager** may **commit**, **push**, open the **PR** and update the
   **tracker** after the gates pass. On an overnight job the PR may be a
   draft after a green gate on the exact tree; the manager owns it. Scribe
   arrives in phase 2, so the tracker update stays with the manager.
