import { connectionsData } from "@/app/[lang]/(dashboard-layout)/pages/account/_data/connections"

import { ProfileContentConnectionItem } from "./profile-content-info-connection-item"

export function ProfileContentConnectionList() {
  return (
    <ul className="grid gap-y-3">
      {connectionsData.map((connection) => (
        <ProfileContentConnectionItem key={connection.name} data={connection} />
      ))}
    </ul>
  )
}
