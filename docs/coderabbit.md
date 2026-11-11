# CodeRabbit reviews

The root `.coderabbit.yaml` configures reviews for the standalone web
repository. The assertive profile asks for detailed findings with a principal
engineer's teaching tone: explain the concrete failure, its impact, and a
proportional fix. Useful diagrams remain enabled; poems, fortunes, and chat
artwork are disabled. CI remains authoritative for actual test and build
execution.

## Review coverage

All source remains eligible. Filters exclude only dependency directories, local
state, and generated Vite output. Tests, migrations, dependency locks, and the
OpenAPI contract stay in scope. Positive allowlists from other stacks can hide
this application's code and must not be copied into this configuration.

Path instructions cover Python across all Django apps, migrations, TypeScript,
templates, tests and shared fixtures, Markdown, container/runtime configuration,
dependency/runtime pins, and CI. Project operations and background tasks have
additional ownership, failure-preservation, and execution-status checks.
Documentation reviews compare names, signatures, permissions, errors, state
transitions, commands, and performance claims with the implementation. Changes
to behavior should also prompt review of the affected documentation.

`AGENTS.md` supplies repository policy. Explicit `files`/`applyTo` mappings make
the coding and XSS guidance under `docs/` apply throughout the source tree.
Admin-operation, map-architecture, and dependency-update documents are mapped to
their affected paths; map architecture guidance is limited to map modules and
entrypoints. GitLab fixture guidance covers shared test support. Other
documentation remains contextual evidence, not automatically a global rule.

Findings must identify severity, affected lines, a reachable failure, and a
small correction. Reviewers trace callers and consolidate duplicate symptoms;
uncertain context is not proof of a defect. Current owner directives take
precedence over stale descriptive documentation.

## Automation and quality checks

Reviews run on new pushes to PRs targeting the default branch, `master`, or
`dev`. Branch expressions are anchored regular expressions. Draft PRs, titles
containing `[wip]`, and PRs labeled `skip-review` or `no-review` are excluded.
Dependabot and test-only PRs remain eligible. Automatic pausing is disabled to
support successive review/fix cycles; rate limits still apply.

Automatic approvals remain disabled. Pre-merge checks warn about titles,
descriptions, linked-issue coverage, and six concrete application risks:

- contradictions between behavior and documentation;
- sensitive output reaching an unauthorized audience;
- scope expansion without an evidenced requirement;
- consequential behavior lacking proportionate regression coverage;
- undisclosed contract changes, stale callers, or damaged persisted identities;
- incomplete coverage of applicable shared map behavior.

Each custom check specifies its passing cases and avoids inferring requirements
or successful verification from missing evidence. These warnings do not replace
GitHub branch protection. Numeric docstring coverage checks are disabled;
documentation is judged by its contracts and accuracy, not a quota. Optional
docstring generation remains available when requested.

Input-transformation checks include type validation before string operations,
empty results after normalization, repeated sanitization, and rejected mutations
that must preserve prior state. These checks supplement output encoding rather
than treating sanitized input as trusted HTML.

Review progress is reported, and a review stopped by an error reports failure.
This does not create branch protection or turn warning findings into merge
blocks; rate-limited reviews are not failed by this setting.

The configuration explicitly enables GitHub check analysis, Ruff, ESLint, secret
scanning, Semgrep, YAML/Markdown linting, ShellCheck, actionlint, and Hadolint.
Ruff and ESLint point to the repository configurations. CodeRabbit's hosted tool
versions and available execution context can differ from local CI; reviewers
must distinguish a hosted-tool limitation from an application defect.

Docstring and unit-test finishing touches are enabled for requested generation,
with instructions preserving existing comments, meaningful coverage, real
clocks, and container-only execution. Interactive chat replies and web context
are enabled. Learnings, issue context, and PR context are repository-local to
avoid applying unrelated organization conventions. Early-access features remain
disabled.

## Validation and settings

Use the current
[configuration reference](https://docs.coderabbit.ai/reference/configuration)
and
[guideline scoping documentation](https://docs.coderabbit.ai/knowledge-base/code-guidelines)
when changing settings. Validate against the schema referenced in the YAML,
including unknown property names, and run the YAML/Markdown hooks in the
existing application container. Review changes here alongside
`.coderabbit.yaml`.

Key controls are `reviews.profile`, `reviews.auto_review`,
`reviews.path_filters`, `reviews.path_instructions`, `reviews.pre_merge_checks`,
`reviews.tools`, `reviews.auto_approvals`, `knowledge_base`, and
`code_generation`. Configuration affects the external review service, not
application runtime performance. It must be published before CodeRabbit can
consume it; local validation does not verify the remote bot's effective settings
or plan-dependent capabilities.
