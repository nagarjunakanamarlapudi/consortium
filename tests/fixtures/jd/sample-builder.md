---
name: sample-builder
description: Build a scoped change with tests.
tools: Read, Grep, Glob, Bash, Edit, Write
consortium:
  version: 1
  station: build
  mode: worktree-write
  write_scope: all
  capabilities: [read, search, shell, edit, toolchain]
  tier: deep
  app: codex
  timeout_minutes: 45
  locks: [test-stack]
  report: findings.v1
  alt_reports: []
---

Implement the brief and run its named tests.
