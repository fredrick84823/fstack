# Cluster a week of sessions into recurring tasks

You are reading one week of a single developer's interactive Claude Code sessions.
Each session under ===SESSIONS=== shows its id, project, the skills it invoked, and the
first prompts the human typed. ===INSTALLED_SKILLS=== lists every installed skill as
`name: description`.

Find **recurring tasks**: the same kind of work, done by the same repeatable procedure,
in **at least 3 different sessions**. These feed a weekly review of which skills to
create and which existing skills are being bypassed.

## Rules

- Group by procedure, not by project or topic. "Write a PR description" in three repos
  is one task; three unrelated questions about the same repo are not.
- A task needs a procedure someone could write down as steps. Open-ended discussion,
  debugging one specific bug, or one-off questions are not tasks. Leave them out.
- Cite only session ids that appear under ===SESSIONS===. Put a session in at most one
  cluster. Fewer than 3 sessions is not a cluster: leave it out.
- `existing_skill`: the exact `name` of an installed skill whose description covers the
  task, whether or not the sessions invoked it. null only when no installed skill covers
  it. Do not invent names.
- `invoker_hints`: words the human actually typed, not your paraphrase.
- Sessions whose prompts are another agent's brief (a task spec handed to a worker,
  a report-back instruction) are not the human's own work. Leave them out.
- Returning zero clusters is a valid answer. Precision over recall.
