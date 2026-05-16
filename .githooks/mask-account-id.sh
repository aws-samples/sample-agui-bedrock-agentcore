#!/usr/bin/env bash
# Git clean filter: mask 12-digit AWS account IDs as <ACCOUNT-ID>.
# Runs on stdin -> stdout whenever git stages content for a configured path.
#
# Caveats this filter knowingly accepts:
#   - Any 12-digit run gets masked, including legitimate non-account-ID numbers
#     (timestamps, IDs that happen to be 12 digits). This is by design — false
#     positives are safer than false negatives for a redaction filter.
#   - Account IDs split across lines or embedded in non-ASCII contexts won't be
#     caught. Keep them on one line in source files.
#
# To bypass for a single commit (e.g. you genuinely need the literal digits):
#   git -c filter.maskaccountid.clean=cat add <file>

# \b doesn't anchor on digit boundaries reliably across sed implementations,
# so we use lookarounds via perl which is universally available.
exec perl -pe 's/(?<![0-9])[0-9]{12}(?![0-9])/<ACCOUNT-ID>/g'
