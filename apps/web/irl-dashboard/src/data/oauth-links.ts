import { SiFacebook, SiGithub, SiGoogle, SiX } from "react-icons/si"

import type { OAuthLinkType } from "../types"

export const oauthLinksData: OAuthLinkType[] = [
  { href: "/", label: "Facebook", icon: SiFacebook },
  { href: "/", label: "GitHub", icon: SiGithub },
  { href: "/", label: "Google", icon: SiGoogle },
  { href: "/", label: "X", icon: SiX },
]
