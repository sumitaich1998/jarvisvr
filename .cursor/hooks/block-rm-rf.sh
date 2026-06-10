#!/bin/bash
# JarvisVR safety hook: block `rm -rf` (and any recursive+force `rm`) before execution.
# Returns permission "deny" so the user is NOT prompted for approval; the agent is told
# to delete files individually instead. Fails open (never blocks unrelated commands).

input=$(cat)

is_rm_rf() {
  local c="$1"

  # Case 1: merged short flags that contain both recursive (r/R) and force (f),
  # e.g. -rf, -fr, -Rf, -fR, -rfv, -rfi, etc.
  if printf '%s' "$c" | grep -Eiq 'rm[[:space:]]+-[[:alnum:]]*r[[:alnum:]]*f'; then return 0; fi
  if printf '%s' "$c" | grep -Eiq 'rm[[:space:]]+-[[:alnum:]]*f[[:alnum:]]*r'; then return 0; fi

  # Case 2: a recursive flag AND a force flag as separate/long tokens on an `rm` command,
  # e.g. `rm -r -f`, `rm -f -R`, `rm --recursive --force`, `rm -r --force`.
  if printf '%s' "$c" | grep -Eq '(^|[^[:alnum:]_])rm([[:space:]]|$)'; then
    local has_recursive=0 has_force=0
    if printf '%s' "$c" | grep -Eq '(^|[[:space:]])(-[rR]|--recursive)([[:space:]]|=|$)'; then has_recursive=1; fi
    if printf '%s' "$c" | grep -Eq '(^|[[:space:]])(-f|--force)([[:space:]]|=|$)'; then has_force=1; fi
    if [ "$has_recursive" -eq 1 ] && [ "$has_force" -eq 1 ]; then return 0; fi
  fi

  return 1
}

if is_rm_rf "$input"; then
  cat <<'JSON'
{
  "permission": "deny",
  "user_message": "Blocked an `rm -rf` style command (JarvisVR safety hook). No approval needed — the agent has been told to delete files individually instead.",
  "agent_message": "POLICY (JarvisVR safety hook): recursive force-delete is disabled in this workspace. Do NOT run `rm -rf` or any recursive+force `rm` (e.g. `rm -r -f`, `rm --recursive --force`). Instead: delete specific files individually with `rm <file>` (or the Delete tool), remove an empty directory with `rmdir <dir>`, or delete a directory's known contents file-by-file. If a whole directory tree genuinely must be removed, ask the user to do it themselves rather than retrying a recursive delete."
}
JSON
  exit 0
fi

# Not a recursive force-delete: stay out of the way and let normal handling proceed.
exit 0
