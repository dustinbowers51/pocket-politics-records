# pocket-politics-records
Hourly refresh of verified public government records for Pocket Politics.

## Decision to publish debate quotes — November 24, 2026

The owner approved automatic publication and accepted that an accurately attributed quotation can be a weak explanation. Both fresh tests failed the original editorial threshold. Across 38 independently checked quotes there were zero wrong speakers, wrong passage votes or altered quotations. Reviewers counted three weak quotes in the first test and five in the second. This is a product decision to publish despite those results, without rescoring or further tuning.

The initial 32 bills comprise 20 stored holdout outputs and 12 earlier pilot bills processed afresh by the daily selector. Eight named weak quotes were excluded from the stored outputs, followed by equal-side trims. Empty states remain part of the release. The daily records workflow covers House and Senate passage votes from launch onward. It retries missing debate-date Records daily until 14 days after passage. The UI contract is “From the official debate. Exact quotes, selected by AI.” Every displayed point has a “Read the full passage” link. Each vote record supplies the tally and official Record link for the empty state.

The hourly publisher reads only the completed snapshot into the content-addressed metadata object. Debate generation, per-bill checkpoints and the monthly OpenAI allowance are independent of hourly refresh. A failed or budget-limited batch cannot replace the published snapshot. Charges are reserved durably before sending requests. An interrupted job conservatively retains its reservation. The production generation limit is $5 per UTC calendar month.

### Owner controls

Open this repository in GitHub → Settings → Secrets and variables → Actions → Variables. Create or edit the repository variable `DEBATE_QUOTES_ENABLED`. Set its value to `false` to hide every debate quote and suspend new generation. Set it to `true` to resume. The next successful hourly publication carries the change. An unset variable defaults to enabled.

Post a new comment on [the pinned removals issue](https://github.com/dustinbowers51/pocket-politics-records/issues/7), for example `drop H.R. 7567 Lucas`. Only GitHub user ID 318668238 may issue commands. A successful removal also trims the opposite side as needed. The [published-debate state branch](https://github.com/dustinbowers51/pocket-politics-records/tree/published-debate/debate-data) holds the permanent exclusion list and command receipts in state.json and the append-only quote history in history.jsonl. Each completed release is traceable through its Git revision, manifest version and SHA-256 metadata object.
