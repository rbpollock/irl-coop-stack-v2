#!/usr/bin/env bash
# Rebuild shadcn-mail's compiled CSS from colors.less + the (committed) LESS
# source tree. Colors are mapped from the dashboard's shadcn tokens in
# globals.css; see styles/colors.less. Requires `less` (via npx).
#
#   bash skins/shadcn-mail/build.sh
set -euo pipefail
SKIN="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SKIN/styles"
npx --yes --package=less lessc styles.less styles.min.css
npx --yes --package=less lessc embed.less embed.min.css
npx --yes --package=less lessc print.less print.min.css
echo "compiled styles.min.css, embed.min.css, print.min.css"
