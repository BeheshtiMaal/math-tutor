---
name: weekly-report
description: Write a weekly report from a sales table - summary first, then the numbers, then suggested actions.
---

# Weekly report

## When to use
The user asks for a weekly or periodic report from tabular data.

## Steps
1. Read the table with `read_table`; never guess its columns.
2. Compute totals and changes with `aggregate_table` and `calculate`.
3. Write the report to a Markdown file in the workspace:
   a three-line management summary, the key numbers with their source, then suggested actions.
4. Tell the user where the file is.
